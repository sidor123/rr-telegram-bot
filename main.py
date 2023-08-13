from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import operator
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import apsched
from datetime import datetime, timedelta

from config import TOKEN_API
from sqlite import Database, Lessons, Students, Admins


class AddLessonsStatesGroup(StatesGroup):  # машина состояний для добавления занятий
    lessons_add_time = State()
    lessons_add_subject = State()
    lessons_add_description = State()
    lessons_add_group_id = State()


class EditLessonsStatesGroup(StatesGroup):  # машина состояний для изменения занятий
    lessons_start_edit = State()
    lessons_delete_or_repair = State()
    lessons_edit_time = State()
    lessons_edit_subject = State()
    lessons_edit_description = State()
    lessons_edit_group_id = State()


class AddStudentsStatesGroup(StatesGroup):  # машина состояний для добавления учеников
    students_add_name_surname = State()
    students_add_telegram_id = State()
    students_add_group_id = State()


class EditStudentsStatesGroup(StatesGroup):  # машина состояний для изменения учеников
    students_start_edit = State()
    students_delete_or_repair = State()
    students_edit_name_surname = State()
    students_edit_telegram_id = State()
    students_edit_group_id = State()


class AddAdmin(StatesGroup):
    adding = State()


storage = MemoryStorage()
bot = Bot(TOKEN_API)
dp = Dispatcher(bot, storage=storage)
temp_data = []
db = Database()
students = Students()
lessons = Lessons()
admins = Admins()

student_kb = ReplyKeyboardMarkup(resize_keyboard=True)  # клавиатура ученика
student_kb.add(KeyboardButton("список занятий"))
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)  # клавиатура администратора, главная клавиатура
main_kb.add(KeyboardButton("добавить занятие")).insert(KeyboardButton("добавить ученика"))
main_kb.add(KeyboardButton("просмотреть занятия")).insert(KeyboardButton("просмотреть учеников"))
main_kb.add(KeyboardButton("изменить занятия")).insert(KeyboardButton("изменить учеников"))
main_kb.add(KeyboardButton("проверить активность")).insert(KeyboardButton("добавить администратора"))
cancel_kb = ReplyKeyboardMarkup(resize_keyboard=True)  # клавиатура с кнопкой "отмены"
cancel_kb.add(KeyboardButton("отмена"))
inf_math_kb = ReplyKeyboardMarkup(resize_keyboard=True)  # клавиатура с кнопками выбора предмета
inf_math_kb.add(KeyboardButton("информатика")).insert(KeyboardButton("математика")).add(KeyboardButton("отмена"))
delete_repair_kb = ReplyKeyboardMarkup(resize_keyboard=True)  # клавиатура с кнопками выбора действия
delete_repair_kb.add(KeyboardButton("удалить")).insert(KeyboardButton("изменить")).add(KeyboardButton("отмена"))

ADMIN = 672708720
scheduler = AsyncIOScheduler(timezone="Asia/Yekaterinburg")  # часовой пояс для шедулера


class AdminMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        if message.text == 'добавить занятие' or message.text == 'добавить ученика' or \
                message.text == 'просмотреть занятия' or message.text == 'просмотреть учеников' or \
                message.text == 'изменить занятия' or message.text == 'изменить учеников' or \
                message.text == 'проверить активность' or message.text == 'добавить администратора':
            if str(message.from_user.id) not in await admins.get_admins():  # блокировка попытки вызвать админские команды учеником
                raise CancelHandler()
        elif message.text == '/start' and str(message.from_user.id) not in await admins.get_admins():  # /start для учеников определяется тут
            await message.answer("Добро пожаловать в наш бот!", reply_markup=student_kb)
            await message.answer("Ваш телеграм ID —", str(message.from_user.id))
            raise CancelHandler()


async def on_startup(_):
    scheduler.start()


async def check_jobs():  # обновление работы шедулера
    for data in await lessons.see_entry("*"):  # берем данные всех занятий
        date = datetime(data[3], data[2], data[1], int(str(data[4][:-2])), int(str(data[4][-2:]))) - timedelta(days=1)
        if date >= datetime.now():  # если дата занятия позже текущей даты более чем на день
            scheduler.add_job(apsched.send_message_to_students, trigger='date',  # добавляем в шедулер уведомление
                              run_date=date,
                              args=[data[-1]])


@dp.message_handler(text='отмена', state='*')  # отменяет любую выполняемую операцию
async def cmd_cancel(message: types.Message, state: FSMContext, text="❌ Операция отменена") -> None:
    await message.answer(text, reply_markup=main_kb, parse_mode='HTML')
    await state.finish()


@dp.message_handler(commands='start')  # вызывает клавиатуру для работы с ботом
async def cmd_start(message: types.Message) -> None:
    await message.answer("❗ Бот начал работу", reply_markup=main_kb)


# БЛОК С ADD STUDENTS
@dp.message_handler(text='добавить ученика')  # блок позволяет добавить нового ученика в бд
async def cmd_add_student(message: types.Message, state: FSMContext) -> None:
    await message.answer("⚙ Введите фамилию и имя ученика", reply_markup=cancel_kb)
    await AddStudentsStatesGroup.students_add_name_surname.set()


@dp.message_handler(state=AddStudentsStatesGroup.students_add_name_surname)  # добавляет имя и фамилию ученика
async def cmd_add_name(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 2:  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['name'] = message.text.split()[1]
        data['surname'] = message.text.split()[0]
    await message.answer("⚙ Введите телеграм ID ученика")
    await AddStudentsStatesGroup.next()


@dp.message_handler(state=AddStudentsStatesGroup.students_add_telegram_id)  # добавляет телеграм ID ученика
async def cmd_add_tel(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['telegram_id'] = message.text
    await message.answer("⚙ Введите номер группы")
    await AddStudentsStatesGroup.next()


@dp.message_handler(state=AddStudentsStatesGroup.students_add_group_id)  # добавляет номер группы и записывает изменения
async def cmd_add_group_id(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['group_id'] = message.text
    await message.answer("✔ Ученик добавлен в БД", reply_markup=main_kb)
    await students.add_entry(state)
    await state.finish()


# КОНЕЦ БЛОКА


# БЛОК С SEE STUDENTS
@dp.message_handler(text='просмотреть учеников')  # выводит в диалог список занятий,
# дата которых назначена позже даты вызова функции
async def cmd_see_students(message: types.Message, state: FSMContext) -> None:
    if not await students.see_entry():
        await cmd_cancel(message, state, "❌ Список ваших учеников <b>пуст</b>!")
        return
    message_text = "<b>⚙ Список ваших учеников:</b>\n"
    for row in await students.see_entry():
        message_text += f'— <b>ID{str(row[0])}</b> {str(row[1])} {str(row[2])} | ' \
                        f'{str(row[3])} | <b>Группа: {str(row[4])}</b>\n'
    await message.answer(message_text, parse_mode='HTML')


# КОНЕЦ БЛОКА


# БЛОК С EDIT STUDENTS
@dp.message_handler(text='изменить учеников')  # меняет запись ученика в бд по ID ученика
async def cmd_edit_students(message: types.Message, state: FSMContext) -> None:
    await message.answer("⚙ Введите ID ученика", reply_markup=cancel_kb)
    await EditStudentsStatesGroup.students_start_edit.set()


@dp.message_handler(state=EditStudentsStatesGroup.students_start_edit)  # выводит запись в чат
async def cmd_check_students_id(message: types.Message, state: FSMContext) -> None:
    global temp_data
    if not message.text.isdigit():
        await cmd_cancel(message, state, "❌ Некорректный ввод")
        return
    async with state.proxy() as data:
        data['id'] = int(message.text)
    if not await students.check_a_by_b('*', 'id', int(message.text)):
        await cmd_cancel(message, state, "❌ Ученика с таким ID <b>нет</b> в БД!")
        return
    else:
        for row in await students.check_a_by_b('*', 'id', int(message.text)):
            temp_data = row
            await message.answer(text=f'⚙ Запись: {str(row[1])} {str(row[2])} | {str(row[3])} | <b>Группа:</b>'
                                      f' {str(row[4])}\n❓ Изменить или удалить запись?',
                                 parse_mode='HTML', reply_markup=delete_repair_kb)
        await EditStudentsStatesGroup.next()


@dp.message_handler(state=EditStudentsStatesGroup.students_delete_or_repair)  # удалить или изменить запись
async def cmd_repair_or_delete_students(message: types.Message, state: FSMContext) -> None:
    if message.text.lower() == "изменить":
        await message.answer(text="⚙ Введите имя и фамилию ученика",
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                             .add(KeyboardButton(f"{temp_data[1]} {temp_data[2]}")).add(KeyboardButton("отмена")))
        await EditStudentsStatesGroup.next()
    elif message.text.lower() == "удалить":
        async with state.proxy() as data:
            await students.delete_entry(data['id'])
        await message.answer("✔ Запись успешно удалена", reply_markup=main_kb)
        await state.finish()
    else:
        await cmd_cancel(message, state, "❌ Введите <b>изменить</b> или <b>удалить</b>!")
        return


@dp.message_handler(state=EditStudentsStatesGroup.students_edit_name_surname)  # меняет имя и фамилию
async def cmd_edit_name_surname(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 2:  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['name'] = message.text.split()[0]
        data['surname'] = message.text.split()[1]
    await EditStudentsStatesGroup.next()
    await message.answer("⚙ Введите телеграм ID ученика", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                         .add(KeyboardButton(temp_data[3])).add(KeyboardButton("отмена")))


@dp.message_handler(state=EditStudentsStatesGroup.students_edit_telegram_id)  # меняет telegram ID
async def cmd_edit_tg_id(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['telegram_id'] = message.text
    await EditStudentsStatesGroup.next()
    await message.answer("⚙ Введите номер группы", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                         .add(KeyboardButton(temp_data[4])).add(KeyboardButton("отмена")))


@dp.message_handler(state=EditStudentsStatesGroup.students_edit_group_id)  # поменять ID группы и применить изменения
async def cmd_edit_students_group_id(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['group_id'] = message.text
    await students.edit_entry(state)
    await state.finish()
    await message.answer("✔ Запись успешно обновлена", reply_markup=main_kb)


# КОНЕЦ БЛОКА


# БЛОК С ADD LESSONS
@dp.message_handler(text='добавить занятие')  # добавляет новые занятия в бд
async def cmd_add_lessons(message: types.Message) -> None:
    await message.answer("⚙ Введите число, месяц, год и время занятия (к примеру, 01-07-2023 10:00)",
                         reply_markup=cancel_kb)
    await AddLessonsStatesGroup.lessons_add_time.set()


@dp.message_handler(state=AddLessonsStatesGroup.lessons_add_time)  # устанавливает время занятия
async def cmd_time_analyze(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 2 or len(message.text.split()[0].split('-')) != 3:  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['day'] = message.text.split()[0].split('-')[0]
        data['month'] = message.text.split()[0].split('-')[1]
        data['year'] = message.text.split()[0].split('-')[2]
        data['time'] = message.text.split()[1].replace(':', '')
    await message.answer("⚙ Введите название предмета (информатика или математика)", reply_markup=inf_math_kb)
    await AddLessonsStatesGroup.next()


@dp.message_handler(state=AddLessonsStatesGroup.lessons_add_subject)  # устанавливает предмет
async def cmd_subject_analyze(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or (
            message.text != 'математика' and message.text != 'информатика'):  # проверка на
        # корректное название предмета
        await cmd_cancel(message, state, "❌ Введите <b>математика</b> или <b>информатика</b>!")
        return
    async with state.proxy() as data:
        data['subject'] = message.text.lower()
    await message.answer("⚙ Введите описание занятия (о чём будет занятие)", reply_markup=cancel_kb)
    await AddLessonsStatesGroup.next()


@dp.message_handler(state=AddLessonsStatesGroup.lessons_add_description)  # устанавливает описание
async def cmd_description_analyze(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data['desc'] = message.text
    await message.answer("⚙ Введите номер группы")
    await AddLessonsStatesGroup.next()


@dp.message_handler(state=AddLessonsStatesGroup.lessons_add_group_id)  # устанавливает ID группы
async def cmd_group_id_analyze(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 and not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['group_id'] = message.text
        date = datetime(int(data['year']), int(data['month']), int(data['day']), int(str(data['time'][:-2])),
                        int(str(data['time'][-2:]))) - timedelta(days=1)
        if date >= datetime.now():
            scheduler.add_job(apsched.send_message_to_students, trigger='date',
                              run_date=date,
                              args=[data['group_id']])
            await check_jobs()
    await message.answer("✔ Занятие добавлено в БД", reply_markup=main_kb)
    await lessons.add_entry(state)
    await state.finish()


# КОНЕЦ БЛОКА


# БЛОК С SEE LESSONS
@dp.message_handler(text='просмотреть занятия')  # выводит в диалог список занятий,
# дата которых назначена позже даты вызова функции
async def cmd_see_lessons(message: types.Message, state: FSMContext) -> None:
    if not await lessons.see_entry('*'):
        await cmd_cancel(message, state, "❌ Список ваших занятий <b>пуст</b>!")
        return
    message_text = "<b>⚙ Список ваших занятий:</b>\n"
    for row in await lessons.see_entry('*'):
        message_text += f'— <b>ID{str(row[0])}</b> {str(row[1])}.{str(row[2])}.{str(row[3])} {str(row[4])[:-2]}:{str(row[4])[-2:]} — {str(row[5])} ({str(row[6])}) <b>Группа: {str(row[7])}</b>\n'
    await message.answer(message_text, parse_mode='HTML')


# КОНЕЦ БЛОКА


# БЛОК С EDIT LESSONS
@dp.message_handler(text='изменить занятия')  # меняет запись занятия в бд по ID занятия
async def cmd_edit_lessons(message: types.Message, state: FSMContext) -> None:
    await message.answer("⚙ Введите ID занятия:", reply_markup=cancel_kb)
    await EditLessonsStatesGroup.lessons_start_edit.set()


@dp.message_handler(state=EditLessonsStatesGroup.lessons_start_edit)  # выводит запись в чат
async def cmd_edit_start(message: types.Message, state: FSMContext) -> None:
    global temp_data
    if not message.text.isdigit():
        await cmd_cancel(message, state, "❌ Некорректный ввод")
        return
    async with state.proxy() as data:
        data['id'] = int(message.text)
    if not await lessons.check_a_by_b('*', 'id', int(message.text)):  # если нет такого занятия
        await cmd_cancel(message, state, "❌ Занятия с таким ID <b>нет</b> в БД!")
        return
    else:
        for row in await lessons.check_a_by_b('*', 'id', int(message.text)):
            temp_data = row
            await message.answer(
                text=f'⚙ Запись: {str(row[1])}-{str(row[2])}-{str(row[3])} | {str(row[4])[:-2]}:{str(row[4])[-2:]} | '
                     f'{str(row[5])} | {str(row[6])} | {str(row[7])}\n❓ Изменить или удалить запись?',
                parse_mode='HTML', reply_markup=delete_repair_kb)
        await EditLessonsStatesGroup.next()


@dp.message_handler(state=EditLessonsStatesGroup.lessons_delete_or_repair)  # определяет, хочет ли пользователь изменить
# или удалить запись
async def what_to_do(message: types.Message, state: FSMContext) -> None:
    if message.text.lower() == "изменить":
        await message.answer(text="⚙ Введите число, месяц, год и время занятия (к примеру, 01-07-2023 10:00)",
                             reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                             .add(
                                 f"{temp_data[1]}-{temp_data[2]}-{temp_data[3]} {temp_data[4][:-2]}:{temp_data[4][-2:]}")
                             .add(KeyboardButton("отмена")))  # сохраняет предыдущую дату и добавляет ее в кнопку
        await EditLessonsStatesGroup.next()
    elif message.text.lower() == "удалить":  # удаляет запись
        async with state.proxy() as data:
            await lessons.delete_entry(data['id'])
        await message.answer("✔ Запись успешно удалена", reply_markup=main_kb)
        await state.finish()
    else:  # идем далее и меняем запись
        await cmd_cancel(message, state, "❌ Введите <b>изменить</b> или <b>удалить</b>!")
        return


@dp.message_handler(state=EditLessonsStatesGroup.lessons_edit_time)  # меняет дату, время и предмет
async def cmd_edit_date(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 2 or len(message.text.split()[0].split('-')) != 3:  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['day'] = message.text.split()[0].split('-')[0]
        data['month'] = message.text.split()[0].split('-')[1]
        data['year'] = message.text.split()[0].split('-')[2]
        data['time'] = message.text.split()[1].replace(':', '')
    await EditLessonsStatesGroup.next()
    await message.answer("⚙ Введите название предмета (информатика или математика)",
                         reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("информатика"))
                         .insert(KeyboardButton("математика")).add(KeyboardButton("отмена")))


@dp.message_handler(state=EditLessonsStatesGroup.lessons_edit_subject)  # меняет предмет
async def cmd_edit_subject(message: types.Message, state: FSMContext) -> None:
    if message.text != 'информатика' and message.text != 'математика':
        await cmd_cancel(message, state, "❌ Введите <b>математика</b> или <b>информатика</b>!")
        return
    async with state.proxy() as data:
        data['subject'] = message.text
    await EditLessonsStatesGroup.next()
    await message.answer("⚙ Введите описание занятия (о чём будет занятие)",
                         reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                         .add(KeyboardButton(f"{temp_data[6]}")).add(KeyboardButton("отмена")))


@dp.message_handler(state=EditLessonsStatesGroup.lessons_edit_description)  # меняет описание
async def cmd_edit_desc(message: types.Message, state: FSMContext) -> None:
    async with state.proxy() as data:
        data['desc'] = message.text
    await EditLessonsStatesGroup.next()
    await message.answer("⚙ Введите номер группы", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True)
                         .add(KeyboardButton(f"{temp_data[7]}")).add(KeyboardButton("отмена")))


@dp.message_handler(state=EditLessonsStatesGroup.lessons_edit_group_id)  # меняет ID группы и применяет изменения
async def cmd_edit_group_id(message: types.Message, state: FSMContext) -> None:
    if len(message.text.split()) != 1 or not message.text.isdigit():  # проверка корректности ввода
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    async with state.proxy() as data:
        data['group_id'] = message.text
        date = datetime(int(data['year']), int(data['month']), int(data['day']), int(str(data['time'][:-2])),
                        int(str(data['time'][-2:]))) - timedelta(days=1)  # дату на день назад, для уведомления
        if date >= datetime.now():  # код ниже очищает все планировки и добавляет их по новой с изменением
            scheduler.remove_all_jobs()
            scheduler.add_job(apsched.send_message_to_students, trigger='date',
                              run_date=date,
                              args=[data['group_id']])
            await check_jobs()
    await lessons.edit_entry(state)
    await state.finish()
    await message.answer("✔ Запись успешно обновлена", reply_markup=main_kb)


# КОНЕЦ БЛОКА

# БЛОК С CHECK ACTIVITY
@dp.message_handler(text='проверить активность')  # большой блок с отчетом о присутствии/отсутствии учеников на занятиях
async def check_activity(message: types.Message) -> None:
    message_text = ''
    for info in await Lessons().check_a_by_b('*', '-', '-'):  # просматриваем все занятия
        message_text += f"— <b>ID{info[0]}</b> <b>Дата</b>: " \
                        f"{datetime(info[3], info[2], info[1], int(info[4][:-2]), int(info[4][-2:]))} " \
                        f"<b>Группа: </b>{info[7]}\n"  # информация о занятии
        undefined_students = await Students().check_a_by_b('name, surname', 'group_id', info[7])  # берем имя и
        # фамилию учеников из целой группы, закрепленной за занятием
        present_students_id = await Lessons().check_a_by_b('present_students', 'id', info[0])  # берем телеграм id
        # учеников, которые будут присутствовать
        present_students = ''
        not_present_students_id = await Lessons().check_a_by_b('not_present_students', 'id', info[0])
        not_present_students = ''
        for student_id in present_students_id[0][0].split('/'):  # берем телеграм id из списка присутствующих
            if student_id:  # добавляем имя и фамилию учеников в созданный список
                if present_students:
                    present_students.append((await Students().check_a_by_b('name, surname', 'telegram_id', student_id))[0])
                else:
                    # тут создаётся список
                    present_students = await Students().check_a_by_b('name, surname', 'telegram_id', student_id)
        for student_id in not_present_students_id[0][0].split('/'):  # тут берем из списка отсутствующих
            if student_id:
                if not_present_students:
                    not_present_students.append((await Students().check_a_by_b('name, surname', 'telegram_id', student_id))[0])
                else:
                    not_present_students = await Students().check_a_by_b('name, surname', 'telegram_id', student_id)
        # ниже перебираем учеников из двух списков, что убрать лишние имена из списка "неопределенных"
        for n in range(len(present_students)):
            if present_students[n] in undefined_students:  # убираем присутствующих
                undefined_students.remove(present_students[n])
        for n in range(len(not_present_students)):
            if not_present_students[n] in undefined_students:  # убираем отсутствующих
                undefined_students.remove(not_present_students[n])
        # ниже формируем текстовую информацию из трех списков
        if present_students:
            message_text += "   ✔ <b>Будут присутствовать:</b> \n"
            for student in present_students:
                if student:
                    message_text += f"       — {student[1]} {student[0]}\n"
        if not_present_students:
            message_text += "   ✖ <b>Будут отсутствовать:</b> \n"
            for student in not_present_students:
                if student:
                    message_text += f"       — {student[1]} {student[0]}\n"
        if undefined_students:
            message_text += "   ❓ <b>Неопределённые:</b> \n"
            for student in undefined_students:
                if student:
                    message_text += f"       — {student[1]} {student[0]}\n"
    if message_text != '':
        await message.answer(text=message_text, parse_mode='HTML')
    else:
        await message.answer("❌ У вас нет запланированных занятий!")


@dp.message_handler(text='добавить администратора')
async def add_admin(message: types.Message, state: FSMContext) -> None:
    await message.answer("⚙ Введите telegram-id администратора", reply_markup=cancel_kb)
    await AddAdmin.adding.set()


@dp.message_handler(state=AddAdmin.adding)
async def admin_accept(message: types.Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await cmd_cancel(message, state, "❌ Некорректный ввод!")
        return
    if message.text in await admins.get_admins():
        await cmd_cancel(message, state, "❌ Администратор уже присутствует в списке!")
        return
    await admins.add_new(message.text)
    await message.answer("✔ Администратор успешно добавлен!", reply_markup=main_kb)
    await state.finish()


@dp.message_handler(text='список занятий')  # выводит список занятий ученика
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    if not await students.check_a_by_b('group_id', 'telegram_id', message.from_user.id):  # если ученика нет в списке
        if str(message.from_user.id) not in await admins.get_admins():  # если юзер не администратор
            await message.answer("❌ Вас <b>нет</b> в списке учеников!", reply_markup=student_kb, parse_mode='HTML')
            return
        await cmd_cancel(message, state, "❌ Вас <b>нет</b> в списке учеников!")  # если команду ввёл администратор
        return
    elif not (await lessons.see_entry((await students.check_a_by_b('group_id', 'telegram_id',
                                                                   message.from_user.id))[0][0])):  # если нет занятий
        if str(message.from_user.id) not in await admins.get_admins():
            await message.answer(text="❌ У вас <b>нет</b> закреплённых занятий!", reply_markup=student_kb,
                                 parse_mode='HTML')
            return
        else:
            await cmd_cancel(message, state, "❌ У вас <b>нет</b> закреплённых занятий!")
            return
    lessons_info = await (lessons.see_entry((await students.check_a_by_b('group_id', 'telegram_id',
                                                                         message.from_user.id))[0][0]))
    lessons_data = []
    for row in lessons_info:
        lessons_data.append([str(row[1]), str(row[2]), str(row[3]), str(row[4]), str(row[5]), str(row[6])])
    lessons_data = sorted(lessons_data, key=operator.itemgetter(2, 1, 0))  # сортировка занятий по дате
    message_text = "<b>❗ Ваш список занятий:</b>\n"
    for date in lessons_data:
        if len(date[0]) == 1:
            date[0] = '0' + date[0]
        if len(date[1]) == 1:
            date[1] = '0' + date[1]
        message_text += f"— <b>{date[0]}.{date[1]}.{date[2]} {date[3][:-2]}:{date[3][-2:]}</b> — {date[4]} ({date[5].capitalize()})\n"
    await message.answer(message_text, parse_mode='HTML')


@dp.callback_query_handler()  # обработка опроса
async def lesson_callback(callback: types.CallbackQuery):  # в качестве callback.data передается id занятия
    if callback.data[:2] != "no":  # callback.data имеет/не имеет в начале "no" для разделения на "да" и "нет"
        await Lessons().set_students_presence(True, callback.from_user.id, int(callback.data))
    else:
        await Lessons().set_students_presence(False, callback.from_user.id, int(callback.data[2:]))


if __name__ == '__main__':
    dp.middleware.setup(AdminMiddleware())
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
