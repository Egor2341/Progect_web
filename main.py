import os
from project_web import db_session
from project_web.users import User
import vk_api
from vk_api import VkUpload
from vk_api.longpoll import VkLongPoll, VkEventType
import random
import wikipedia
import requests
from bs4 import BeautifulSoup
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sys
from requests import request
import pymorphy2

TOKEN = '77ab780075a079af7c67188fd1e66c59417c4ba561aca37fb1b4020bf366fcafb7038b8e3f8a115bda3fb'
API_KEY = '40d1649f-0493-4b70-98ba-98533de7710b'
WEATHER_API = "8494a8a0f63285886b520069bc729ace"
ORG_API = "dda3ddba-c9ea-4ead-9010-f43fbc15c6e3"
API_NEWS = "8a74b144fc324f32b623c24274146570"
search_api_server = "https://search-maps.yandex.ru/v1/"
vk = vk_api.VkApi(token=TOKEN)
upload = VkUpload(vk)
longpol = VkLongPoll(vk)
wikipedia.set_lang("RU")
morph = pymorphy2.MorphAnalyzer()
currencies = {'евро': "EUR", "доллар": "USD", "фунты": "GBP", "юань": "CNY", "рубль": "RUB"}
db_session.global_init("black_list.db")


def get_coordinates(city_name):
    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": "40d1649f-0493-4b70-98ba-98533de7710b",
            'geocode': city_name,
            'format': 'json'
        }
        response = requests.get(url, params)
        json = response.json()
        coordinates_str = json['response']['GeoObjectCollection'][
            'featureMember'][0]['GeoObject']['Point']['pos']
        long, lat = map(float, coordinates_str.split())
        return long, lat
    except Exception as e:
        return e


def show_map(ll_spn=None, map_type="map", add_params=None):
    if ll_spn:
        map_request = f"http://static-maps.yandex.ru/1.x/?{ll_spn}&l={map_type}"
    else:
        map_request = f"http://static-maps.yandex.ru/1.x/?l={map_type}"
    if add_params:
        map_request += "&" + add_params
    response = requests.get(map_request)
    if not response:
        print("Ошибка выполнения запроса:")
        print(map_request)
        print("Http статус:", response.status_code, "(", response.reason, ")")
        sys.exit(1)
    map_file = "map.png"
    try:
        with open(map_file, "wb") as file:
            file.write(response.content)
    except IOError as ex:
        print("Ошибка записи временного файла:", ex)
        sys.exit(2)


def geocode(address):
    geocoder_request = f"http://geocode-maps.yandex.ru/1.x/"
    geocoder_params = {
        "apikey": API_KEY,
        "geocode": address,
        "format": "json"}
    response = requests.get(geocoder_request, params=geocoder_params)

    if response:
        json_response = response.json()

    else:
        raise RuntimeError(
            f"""Ошибка выполнения запроса:
            {geocoder_request}
            Http статус: {response.status_code} ({response.reason})""")

    features = json_response["response"]["GeoObjectCollection"]["featureMember"]
    return features[0]["GeoObject"] if features else None


def get_ll_span(address):
    toponym = geocode(address)
    if not toponym:
        return (None, None)

    toponym_coodrinates = toponym["Point"]["pos"]
    toponym_longitude, toponym_lattitude = toponym_coodrinates.split(" ")
    ll = ",".join([toponym_longitude, toponym_lattitude])
    envelope = toponym["boundedBy"]["Envelope"]
    l, b = envelope["lowerCorner"].split(" ")
    r, t = envelope["upperCorner"].split(" ")
    dx = abs(float(l) - float(r)) / 2.0
    dy = abs(float(t) - float(b)) / 2.0
    span = f"{dx},{dy}"

    return ll, span


def send_messages(chat_id, text):
    random_id = random.randint(0, 10000000)
    vk.method('messages.send', {'chat_id': chat_id, 'message': text, 'random_id': random_id})


def main_keyboard(toponym_to_find=None, org=None):
    keyboard = VkKeyboard()
    buttons = ["Википедия", "Курс валют", "Геокодер"]
    button_colors = [VkKeyboardColor.PRIMARY, VkKeyboardColor.NEGATIVE, VkKeyboardColor.PRIMARY]

    for btn, btn_color in zip(buttons, button_colors):
        keyboard.add_button(btn, btn_color)
    keyboard.add_line()
    keyboard.add_button("Текущая погода в", VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("Новости", VkKeyboardColor.NEGATIVE)
    keyboard.add_button("Организации в", VkKeyboardColor.PRIMARY)
    random_id = random.randint(0, 10000000)

    if toponym_to_find:
        vk.method('messages.send',
                  {'chat_id': chat_id, 'message': f'Это {toponym_to_find.capitalize()}', 'random_id': random_id,
                   'keyboard': keyboard.get_keyboard()})
    elif org:
        vk.method('messages.send',
                  {'chat_id': chat_id, 'message': f'Вот что я нашёл.', 'random_id': random_id,
                   'keyboard': keyboard.get_keyboard()})
    else:
        vk.method('messages.send',
                  {'chat_id': chat_id, 'message': 'Теперь вы видите мой функционал полностью.', 'random_id': random_id,
                   'keyboard': keyboard.get_keyboard()})


for event in longpol.listen():
    if event.type == VkEventType.MESSAGE_NEW:
        if event.to_me:
            if event.from_chat:
                bad_words = ['']
                msg = event.text
                user = vk.method("users.get", {"user_ids": event.user_id})
                chat_id = event.chat_id
                bad = False
                if '[club210161388|@club210161388]' in msg:
                    msg = msg[31:]

                for word in msg.split():
                    if str(word).lower() in bad_words:
                        send_messages(chat_id, 'Вы использовали плохие слова')
                        bad = True
                        db_sess = db_session.create_session()
                        bad_user = User(
                            user_id=event.user_id
                        )
                        db_sess.add(bad_user)
                        db_sess.commit()

                db_sess = db_session.create_session()
                if db_sess.query(User).filter(User.user_id == event.user_id).first():
                    send_messages(chat_id,
                                  f'За использование запрещенных слов взаимодествие с полным функционалом отключено.')
                elif not bad and not db_sess.query(User).filter(User.user_id == event.user_id).first():
                    if 'hello' == str(msg).lower() or 'привет' == str(msg).lower() or 'hello!' == str(
                            msg).lower() or 'привет!' == str(msg).lower():
                        send_messages(chat_id, f'Привет, {user[0]["first_name"]}!')

                    elif msg == "keyboard":
                        main_keyboard()

                    elif 'how are you?' == str(msg).lower() or 'как дела?' == str(msg).lower():
                        send_messages(chat_id, 'Я в порядке, спасибо! А вы?')

                    elif msg == "Геокодер":
                        send_messages(chat_id, 'Что вы хотите увидеть?')
                        for event in longpol.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                keyboard = VkKeyboard(one_time=True)
                                buttons = ["Схема", "Спутник", "Гибрид"]
                                button_colors = [VkKeyboardColor.PRIMARY, VkKeyboardColor.NEGATIVE,
                                                 VkKeyboardColor.POSITIVE]

                                for btn, btn_color in zip(buttons, button_colors):
                                    keyboard.add_button(btn, btn_color)
                                random_id = random.randint(0, 10000000)
                                vk.method('messages.send',
                                          {'chat_id': chat_id, 'message': 'Выберите тип карты', 'random_id': random_id,
                                           'keyboard': keyboard.get_keyboard()})
                                toponym_to_find = event.text

                                for event in longpol.listen():
                                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                        msg = event.text
                                        if '[club210161388|@club210161388]' in msg:
                                            msg = msg[31:]
                                        if msg == 'Схема':
                                            type = "map"
                                        elif msg == 'Спутник':
                                            type = "sat"
                                        elif msg == 'Гибрид':
                                            type = "sat,skl"
                                        else:
                                            type = None
                                        break

                                if toponym_to_find and type:
                                    ll, spn = get_ll_span(toponym_to_find)
                                    ll_spn = f"ll={ll}&spn={spn}"
                                    show_map(ll_spn, type)

                                else:
                                    print('No data')

                                random_id = random.randint(0, 10000000)
                                upload = vk_api.VkUpload(vk)
                                ph = upload.photo_messages('map.png')
                                owner_id, id, access_key = ph[0]['owner_id'], ph[0]['id'], ph[0]['access_key']
                                attachment = f'photo{owner_id}_{id}_{access_key}'
                                vk.method('messages.send',
                                          {'chat_id': chat_id, 'random_id': random_id, 'attachment': attachment})
                                main_keyboard(toponym_to_find=toponym_to_find.lower())
                                os.remove('map.png')
                                break

                    elif msg == 'Википедия':
                        send_messages(chat_id, 'Введите запрос')
                        for event in longpol.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                send_messages(chat_id, f'Вот что я нашел: \n' + str(wikipedia.summary(event.text)))
                                break

                    elif msg == "Курс валют":
                        keyboard = VkKeyboard(one_time=True)
                        buttons = ["Евро", "Доллар", "Фунты"]
                        button_colors = [VkKeyboardColor.PRIMARY, VkKeyboardColor.NEGATIVE,
                                         VkKeyboardColor.POSITIVE]
                        for btn, btn_color in zip(buttons, button_colors):
                            keyboard.add_button(btn, btn_color)
                        keyboard.add_line()
                        buttons = ["Юань", "Рубль"]
                        button_colors = [VkKeyboardColor.PRIMARY,
                                         VkKeyboardColor.NEGATIVE]
                        for btn, btn_color in zip(buttons, button_colors):
                            keyboard.add_button(btn, btn_color)
                        random_id = random.randint(0, 10000000)
                        vk.method('messages.send',
                                  {'chat_id': chat_id,
                                   'message': 'Выберите валюту',
                                   'random_id': random_id,
                                   'keyboard': keyboard.get_keyboard()})
                        for event in longpol.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                msg = event.text.lower()
                                if '[club210161388|@club210161388]' in msg:
                                    msg = msg[31:]
                                if msg in currencies:
                                    first_curr = currencies[msg]
                                else:
                                    send_messages(chat_id, 'Неккоректный ввод')
                                    main_keyboard()
                                    break
                                keyboard = VkKeyboard(one_time=True)
                                buttons = ["Евро", "Доллар", "Фунты", "Юань", "Рубль"]
                                del buttons[buttons.index(msg.capitalize())]
                                button_colors = [VkKeyboardColor.PRIMARY, VkKeyboardColor.NEGATIVE,
                                                 VkKeyboardColor.POSITIVE, VkKeyboardColor.PRIMARY]

                                for btn, btn_color in zip(buttons, button_colors):
                                    keyboard.add_button(btn, btn_color)
                                random_id = random.randint(0, 10000000)
                                vk.method('messages.send',
                                          {'chat_id': chat_id,
                                           'message': 'Выберите валюту, стоймость которой нужно найти',
                                           'random_id': random_id,
                                           'keyboard': keyboard.get_keyboard()})
                                for event in longpol.listen():
                                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                        msg = event.text.lower()
                                        if '[club210161388|@club210161388]' in msg:
                                            msg = msg[31:]
                                        if msg in currencies:
                                            second_curr = currencies[msg]
                                            url = \
                                                f'https://v6.exchangerate-api.com/v6/945d2ab03ce22c6256b18373/latest/{first_curr}'
                                            response = requests.get(url)
                                            if response:
                                                json_response = response.json()
                                                result = json_response["conversion_rates"]
                                                send_messages(chat_id, result[f"{second_curr}"])
                                            main_keyboard()
                                            break
                                        else:
                                            send_messages(chat_id, 'Неккоректный ввод')
                                            main_keyboard()
                                            break
                                break

                    elif msg == 'Новости':
                        titles = []
                        url = f"https://newsapi.org/v2/top-headlines?country=ru&apiKey={API_NEWS}"
                        response = requests.get(url)
                        if response:
                            for i in range(5):
                                json_response = response.json()
                                title = json_response["articles"][i]["title"]
                                titles.append(title)
                        send_messages(chat_id, f'''{titles[0]}
                                                    {titles[1]}
                                                    {titles[2]}
                                                    {titles[3]}
                                                    {titles[4]}''')

                    elif msg == 'Организации в':
                        send_messages(chat_id, 'Укажите город')
                        for event in longpol.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                city_to_find = event.text
                                if city_to_find:
                                    ll, spn = get_ll_span(city_to_find)
                                    ll_spn = f"ll={ll}&spn={spn}"
                                    send_messages(chat_id, 'Что вы хотите найти?')
                                    for event in longpol.listen():
                                        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                            org_to_find = event.text.lower()
                                            res = morph.parse(org_to_find)[0]
                                            if 'NOUN' in res.tag:
                                                org_to_find = morph.parse(org_to_find)[0].normal_form
                                            else:
                                                send_messages(chat_id, 'Нужно указать существительное.')
                                                break
                                            search_params = {
                                                "apikey": ORG_API,
                                                "text": f"{org_to_find}",
                                                "lang": "ru_RU",
                                                "ll": ll,
                                                "type": "biz"
                                            }

                                            response = requests.get(search_api_server, params=search_params)
                                            json_response = response.json()
                                            points = []

                                            for feature in json_response["features"]:
                                                point = feature["geometry"]["coordinates"]
                                                points.append(f"{point[0]},{point[1]},pm2grm")
                                            delta = '0.05'
                                            map_params = {
                                                "ll": ll,
                                                "spn": ",".join([delta, delta]),
                                                "l": "map",
                                                "pt": "~".join(points)
                                            }

                                            map_api_server = "http://static-maps.yandex.ru/1.x/"
                                            response = requests.get(map_api_server, params=map_params)

                                            if not response:
                                                print("Ошибка выполнения запроса:")
                                                print("Http статус:", response.status_code, "(", response.reason, ")")
                                                sys.exit(1)

                                            map_file = "org.png"
                                            with open(map_file, "wb") as file:
                                                file.write(response.content)

                                            random_id = random.randint(0, 10000000)
                                            upload = vk_api.VkUpload(vk)
                                            ph = upload.photo_messages('org.png')
                                            owner_id, id, access_key = ph[0]['owner_id'], ph[0]['id'], ph[0][
                                                'access_key']
                                            attachment = f'photo{owner_id}_{id}_{access_key}'
                                            vk.method('messages.send',
                                                      {'chat_id': chat_id, 'random_id': random_id,
                                                       'attachment': attachment})
                                            main_keyboard(org='org')
                                            os.remove('org.png')
                                            break

                                else:
                                    print('No data')
                                break

                    elif msg == "Текущая погода в":
                        send_messages(chat_id, 'Укажите город.')
                        for event in longpol.listen():
                            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                                lon, lat = get_coordinates(event.text)
                                res = requests.get(
                                    f"https://api.openweathermap.org/data/2.5/"
                                    f"weather?lat={lat}&lon={lon}&appid={WEATHER_API}&lang=ru&units=metric")
                                data = res.json()
                                direction = data['wind']['deg']
                                if 330 <= int(direction) <= 30:
                                    wind = 'С'
                                elif 30 < int(direction) < 60:
                                    wind = 'СВ'
                                elif 60 <= int(direction) <= 120:
                                    wind = 'В'
                                elif 120 < int(direction) < 150:
                                    wind = 'ЮВ'
                                elif 150 <= int(direction) <= 210:
                                    wind = 'Ю'
                                elif 210 < int(direction) < 240:
                                    wind = 'ЮЗ'
                                elif 240 <= int(direction) <= 300:
                                    wind = 'З'
                                else:
                                    wind = 'СЗ'
                                pressure = int(data['main']['pressure'] // 1.33322)
                                send_messages(chat_id, f'''{data['weather'][0]['description']}
                                                            температура: {data['main']['temp']}
                                                            ощущается как: {data['main']['feels_like']}
                                                            атмосферное давление: {pressure} мм рт.ст.
                                                            влажность: {str(data['main']['humidity'])} %
                                                            ветер: {str(data['wind']['speed'])} м/с, {wind}''')
                                break
                    else:
                        send_messages(chat_id, 'Я вас не понял.')
