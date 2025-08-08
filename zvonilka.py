import os
import requests
import hashlib
import hmac
import base64
from urllib.parse import urlencode
from collections import OrderedDict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

ZADARMA_API_KEY = os.environ.get('ZADARMA_API_KEY')
ZADARMA_API_SECRET = os.environ.get('ZADARMA_API_SECRET')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

ENTRY_NUMBER = '101'
EXIT_NUMBER = '102'
INTERNAL_NUMBER = '+380635154798'

class ZadarmaAPI(object):
    def __init__(self, key, secret, is_sandbox=False):
        self.key = key
        self.secret = secret
        self.is_sandbox = is_sandbox
        self.__url_api = 'https://api.zadarma.com'
        if is_sandbox:
            self.__url_api = 'https://api-sandbox.zadarma.com'

    def call(self, method, params={}, request_type='GET', format='json', is_auth=True):
        request_type = request_type.upper()
        if request_type not in ['GET', 'POST', 'PUT', 'DELETE']:
            request_type = 'GET'
        params['format'] = format
        auth_str = None
        is_nested_data = False
        for k in params.values():
            if not isinstance(k, str):
                is_nested_data = True
                break
        if is_nested_data:
            params_string = self.__http_build_query(OrderedDict(sorted(params.items())))
            params = params_string
        else:
            params_string = urlencode(OrderedDict(sorted(params.items())))
        if is_auth:
            auth_str = self.__get_auth_string_for_header(method, params_string)
        if request_type == 'GET':
            result = requests.get(self.__url_api + method + '?' + params_string, headers={'Authorization': auth_str})
        elif request_type == 'POST':
            result = requests.post(self.__url_api + method, headers={'Authorization': auth_str}, data=params)
        elif request_type == 'PUT':
            result = requests.put(self.__url_api + method, headers={'Authorization': auth_str}, data=params)
        elif request_type == 'DELETE':
            result = requests.delete(self.__url_api + method, headers={'Authorization': auth_str}, data=params)
        return result

    def __http_build_query(self, data):
        parents = list()
        pairs = dict()
        def renderKey(parents):
            depth, outStr = 0, ''
            for x in parents:
                s = "[%s]" if depth > 0 or isinstance(x, int) else "%s"
                outStr += s % str(x)
                depth += 1
            return outStr
        def r_urlencode(data):
            if isinstance(data, list) or isinstance(data, tuple):
                for i in range(len(data)):
                    parents.append(i)
                    r_urlencode(data[i])
                    parents.pop()
            elif isinstance(data, dict):
                for key, value in data.items():
                    parents.append(key)
                    r_urlencode(value)
                    parents.pop()
            else:
                pairs[renderKey(parents)] = str(data)
            return pairs
        return urlencode(r_urlencode(data))

    def __get_auth_string_for_header(self, method, params_string):
        data = method + params_string + hashlib.md5(params_string.encode('utf8')).hexdigest()
        hmac_h = hmac.new(self.secret.encode('utf8'), data.encode('utf8'), hashlib.sha1)
        auth = self.key + ':' + base64.b64encode(hmac_h.hexdigest().encode('utf8')).decode()
        return auth

zadarma_api = ZadarmaAPI(ZADARMA_API_KEY, ZADARMA_API_SECRET)

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Въезд", callback_data='entry')],
        [InlineKeyboardButton("Выезд", callback_data='exit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите действие:', reply_markup=reply_markup)

async def button_click(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == 'entry':
        destination = ENTRY_NUMBER
    elif query.data == 'exit':
        destination = EXIT_NUMBER
    else:
        return

    params = {'from': INTERNAL_NUMBER, 'to': destination}
    response = zadarma_api.call('/v1/request/callback/', params=params, request_type='GET')

    if response.status_code == 200:
        await query.edit_message_text(text=f"Звонок на {destination} инициирован.")
    else:
        await query.edit_message_text(text=f"Ошибка при инициировании звонка. Код: {response.status_code}, Ответ: {response.text}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.run_polling()

if __name__ == '__main__':
    main()
