from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from main import bot, lessons, students


async def send_message_to_students(*data):
    info = await lessons.check_a_by_b('*', 'group_id', data[0])
    print(data)
    for row in await students.check_a_by_b('*', 'group_id', data[0]):
        inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton(text="✔", callback_data=str(info[0])),
                                               InlineKeyboardButton(text="❌", callback_data="no" + str(info[0])))
        send_message_text = f"📌 <b>{row[1]} {row[2]}</b>, предупреждаем, через 24 часа ({info[1]}.{info[2]}.{info[3]}" \
                            f" {info[4][:-2]}:{info[4][-2:]}) начнётся занятие по <b>{info[5][:-1]}е</b>.\n" \
                            f"<b>Описание занятия</b> — {info[6]}.\nВыберите ниже," \
                            f" сможете ли вы <b>присутствовать</b> на занятии!"
        await bot.send_message(row[3], send_message_text, parse_mode='HTML', reply_markup=inline_kb)
