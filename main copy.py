"""Telegram bot for tax project"""
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, Application, CommandHandler, \
    MessageHandler, filters, CallbackQueryHandler

from database.mongo import MongoDB, ConversationLog, MassageRating
from processor import Processor
from models.openai import HUMAN_PROMPT_BLANK
from scrip_utils import get_logger, get_kwargs
from settings import TELEGRAM_TOKEN, MONGO_HOST, MONGO_PORT, \
    MONGO_DATABASE, MONGO_USERNAME, MONGO_PASSWORD, MODEL_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

forbidden_user_mess = '''Этот бот является разработкой компании "Технологии Доверия". Для получения доступа к боту напишите, пожалуйста, @si_yu или @bugaev_ms.'''
help_command_text = '''
Для получения ответа на вопрос по налоговой тематике введите его в чат с ботом. 

Ответы на вопросы по другим тематикам могут быть некорректными. 

После получения ответа, оцените его, пожалуйста, нажав на кнопку 👍 или 👎. Если вы неверно оценили ответ, то можно повторно оценить его, нажав на кнопку с другой оценкой. 
'''

async def start(update: Update,
                context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,
                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    if mongo.check_user(update=update)==True:
        reply_text = "Hi!"
    else: 
        reply_text = forbidden_user_mess
    await update.message.reply_text(reply_text)


async def help_command(update: Update,
                       context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,
                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    if mongo.check_user(update=update)==True:
        reply_text = help_command_text
    else: 
        reply_text = forbidden_user_mess
    await update.message.reply_text(reply_text)


async def check_user_params(update: Update,
                            context: ContextTypes.DEFAULT_TYPE,
                            parameter: str,
                            default_value: str = None
                            ) -> None:
    """Check if user specified parameters."""
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,
                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    if mongo.check_user(update=update)==True:
        if parameter not in context.user_data:
            reply_text = f"You have not specified {parameter} yet, " \
                         f"using default value {default_value}"
            await update.message.reply_text(reply_text)
        else:
            reply_text = f"Using  ```\n{parameter}={context.user_data[parameter]}\n```"
            await update.message.reply_markdown(reply_text)
    else:
        reply_text = forbidden_user_mess
        await update.message.reply_text(reply_text)


async def change_prompt(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change prompt passed to model."""
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,
                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    if mongo.check_user(update=update)==True:
        message_parts = update.message.text.split(' ')
        prompt_help_text = ("Your prompt should contain {context} and {question} tags"
                            " to be replaced with context and question respectively."
                            " For example:\n"
                            "```\n/prompt 'Используя контекст: {context} ответь на вопрос: {question}'\n```")
        if len(message_parts) == 1:
            await check_user_params(update, context,
                                    parameter='prompt',
                                    default_value=HUMAN_PROMPT_BLANK)
            reply_text = "Please, specify prompt. \n" + prompt_help_text
            await update.message.reply_markdown(reply_text)
        else:
            prompt = update.message.text.split(' ', maxsplit=1)[1]
            if '{context}' not in prompt or '{question}' not in prompt:
                reply_text = "Please, specify prompt with {context} and {question} tags. \n" + prompt_help_text
                await update.message.reply_markdown(reply_text)
            else:
                context.user_data['prompt'] = prompt
                logger.info(f"Prompt was set to {context.user_data['prompt']}")
                reply_text = f"Selected prompt ```\n{prompt}\n``` was set."
                await update.message.reply_markdown(reply_text)
    else:
        reply_text = forbidden_user_mess
        await update.message.reply_text(reply_text)


async def answer(update: Update,
                 context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,

                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    kwargs = {
        "message_id": update.message.message_id,
        "user_telegram_id": update.effective_user.id,
        "chat_id": update.message.chat.id,
    }
    if mongo.check_user(update=update)==True:
        msg = ConversationLog(
            message_time=update.message.date.timestamp(),
            bot_response=False,
            massage_text=update.message.text,
            message_rating_id=0,
            **kwargs
        )
        mongo.upload_file(msg)
        selected_model = context.user_data.get('model', MODEL_NAME)
        user_prompt = context.user_data.get('prompt', HUMAN_PROMPT_BLANK)
        processor = Processor(
            question=update.message.text,
            selected_model=selected_model,
            prompt=user_prompt,
        )
        reply_text = processor.answer
        reply_source = processor.source
        if not processor.is_model_valid:
            reply_full = reply_text
            reply_msg = await update.message.reply_text(reply_full)
        else:
            if reply_source == '':
                reply_full = reply_text
            else:
                reply_full = reply_text + \
                    '\n\nДля формирования ответа использовались фрагменты из следующих источников:\n' + reply_source
            button1 = InlineKeyboardButton("👍", callback_data='1')
            button2 = InlineKeyboardButton("👎", callback_data='0')
            keyboard = [[button1, button2]]
            reply_msg = await update.message.reply_text(reply_full + '\n\nОцените, пожалуйста, ответ:', reply_markup=InlineKeyboardMarkup(keyboard))
        ans = ConversationLog(
            message_time=datetime.now().timestamp(),
            bot_response=True,
            massage_text=reply_full,
            message_rating_id=reply_msg.message_id,
            **kwargs
        )
        mongo.upload_file(ans)
    else:
        reply_text = forbidden_user_mess
        await update.message.reply_text(reply_text)


async def rating_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """React to rating buttoms push"""
    query = update.callback_query
    await query.answer()
    mongo = MongoDB(host=MONGO_HOST, port=MONGO_PORT,
                    alias='file_db', db_name=MONGO_DATABASE,
                    username=MONGO_USERNAME, password=MONGO_PASSWORD)
    data = update.callback_query.data
    if data == '1':
        ans = MassageRating(
            message_id=query.message.message_id,
            chat_id=query.message.chat.id,
            rating_time=datetime.now().timestamp(),
            rating=1
        )
        mongo.upload_file(ans)
    else:
        ans = MassageRating(
            message_id=query.message.message_id,
            chat_id=query.message.chat.id,
            rating_time=datetime.now().timestamp(),
            rating=0
        )
        mongo.upload_file(ans)


def main() -> None:
    """Start the bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("prompt", change_prompt))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, answer))
    application.add_handler(CallbackQueryHandler(rating_buttons))
    application.run_polling()


if __name__ == "__main__":
    file_name = Path(__file__).stem
    default_config_path = Path(__file__).parent / \
        f"{file_name}_config.yml"
    kwargs = get_kwargs(default_config_path=default_config_path).parse_args()
    LOGGER = get_logger(
        logger_name=file_name,
        level=kwargs.logger_level
    )
    main()
