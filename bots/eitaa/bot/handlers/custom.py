"""منطق نمونه؛ منطق واقعی ربات را در همین فایل گسترش بده."""
from ..core import Bot
bot=Bot()

@bot.on_message(command='start',name='start')
def start(message):
    return {'text':'سلام! ربات نمونه‌ی AutoEitaa آماده است. برای راهنما /help را بفرست.'}

@bot.on_message(command='help',name='help')
def help_handler(message):
    return {'text':'نمونه: پیام را با handler سفارشی در bot/handlers/custom.py پردازش کن.'}

@bot.on_message(pattern=r'(?i)^سلام[!؟ ]*$',name='hello')
def hello(message):
    return {'text':'سلام، خوش اومدی!'}
