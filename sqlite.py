import psycopg2
from datetime import datetime, timedelta

DB_URL = "postgresql://postgres:m8bZUdcT9BRGyzTHhfgn@containers-us-west-135.railway.app:7528/railway"

class Database:
    def __init__(self):
        global db, cur
        db = psycopg2.connect(DB_URL, sslmode="require")
        cur = db.cursor()


class Lessons:
    def __init__(self):
        cur.execute("CREATE TABLE IF NOT EXISTS lessons(id INTEGER PRIMARY KEY, day INTEGER, month INTEGER,"
                    "year INTEGER, time TEXT, subject TEXT, description TEXT, group_id INTEGER, present_students "
                    "TEXT, not_present_students TEXT)")
        db.commit()

    async def add_entry(self, state):
        async with state.proxy() as data:
            cur.execute(f"INSERT INTO lessons (day, month, year, time, subject, description, group_id, "
                        f"present_students, not_present_students) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (data['day'], data['month'], data['year'], data['time'], data['subject'], data['desc'],
                         data['group_id'], "/", "/"))
        db.commit()

    async def see_entry(self, group_id):
        if group_id == '*':
            cur.execute(f"SELECT * FROM lessons")
            record = []
            for data in cur.fetchall():
                if datetime(data[3], data[2], data[1]) >= datetime.now():
                    record.append(data)
                else:
                    cur.execute(f"DELETE FROM lessons WHERE day = {data[1]} AND month = {data[2]} AND year = {data[3]}")
            db.commit()
            return record
        cur.execute(f"SELECT * FROM lessons WHERE group_id = {group_id}")
        record = []
        for data in cur.fetchall():
            if datetime(data[3], data[2], data[1]) >= datetime.now():
                record.append(data)
        return record

    async def delete_entry(self, entry_id):
        cur.execute(f"DELETE FROM lessons WHERE id={entry_id}")
        db.commit()

    async def edit_entry(self, state):
        async with state.proxy() as data:
            cur.execute(f"UPDATE lessons SET day = {str(data['day'])} WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET month = {str(data['month'])} WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET year = {str(data['year'])} WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET time = {str(data['time'])} WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET subject = '{str(data['subject'])}' WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET description = '{str(data['desc'])}' WHERE id = {data['id']}")
            cur.execute(f"UPDATE lessons SET group_id = {str(data['group_id'])} WHERE id = {data['id']}")
        db.commit()

    async def check_a_by_b(self, desired_entry, conditional_entry, entry_data):
        if conditional_entry == '-' and entry_data == '-':
            cur.execute(f"SELECT {desired_entry} FROM lessons")
        else:
            cur.execute(f"SELECT {desired_entry} FROM lessons WHERE {conditional_entry} = {entry_data}")
            if conditional_entry == "group_id":
                for data in cur.fetchall():
                    if (datetime(data[3], data[2], data[1], int(str(data[4])[:-2]), int(str(data[4])[-2:])) - timedelta(days=1)) ==\
                            (datetime(datetime.now().year, datetime.now().month, datetime.now().day, datetime.now().hour,
                                    datetime.now().minute) + timedelta(hours=5)):
                        return data
        return cur.fetchall()

    async def set_students_presence(self, presence, student_id, lesson_id):
        cur.execute("SELECT * FROM lessons")
        record = cur.fetchall()
        print(record)
        cur.execute("SELECT present_students FROM lessons where id = '%s'", (lesson_id, ))
        present_record = cur.fetchone()[0]
        cur.execute("SELECT not_present_students FROM lessons where id = '%s'", (lesson_id, ))
        non_present_record = cur.fetchone()[0]
        if presence:
            if str(student_id) in non_present_record.split('/'):
                non_present_record = non_present_record.replace(str(student_id) + '/', '')
            if str(student_id) not in present_record.split('/'):
                present_record += str(student_id)
                present_record += '/'
        else:
            if str(student_id) in present_record.split('/'):
                present_record = present_record.replace(str(student_id) + '/', '')
            if str(student_id) not in non_present_record.split('/'):
                non_present_record += str(student_id)
                non_present_record += '/'
        cur.execute("UPDATE lessons SET not_present_students = '%s' WHERE id = %s", (not_present_record, lesson_id))
        cur.execute("UPDATE lessons SET present_students = '%s' WHERE id = %s", (present_record, lesson_id))
        db.commit()


class Students:
    def __init__(self):
        cur.execute("CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, "
                    "name TEXT, surname TEXT, telegram_id TEXT, group_id INTEGER)")
        db.commit()

    async def add_entry(self, state):
        async with state.proxy() as data:
            cur.execute("INSERT INTO students (name, surname, telegram_id, group_id) VALUES (%s, %s, %s, %s)",
                        (data['name'], data['surname'], data['telegram_id'], data['group_id']))
        db.commit()

    async def see_entry(self, *entry_id):
        cur.execute(f"SELECT * FROM students")
        return cur.fetchall()

    async def delete_entry(self, entry_id):
        cur.execute(f"DELETE FROM students WHERE id={entry_id}")
        db.commit()

    async def edit_entry(self, state):
        async with state.proxy() as data:
            cur.execute(f"UPDATE students SET name = '{data['name']}' WHERE id = {data['id']}")
            cur.execute(f"UPDATE students SET surname = '{data['surname']}' WHERE id = {data['id']}")
            cur.execute(f"UPDATE students SET telegram_id = {data['telegram_id']} WHERE id = {data['id']}")
            cur.execute(f"UPDATE students SET group_id = {data['group_id']} WHERE id = {data['id']}")
        db.commit()

    async def check_a_by_b(self, desired_entry, conditional_entry, entry_data):
        cur.execute(f"SELECT {desired_entry} FROM students WHERE {conditional_entry} = {entry_data}")
        return cur.fetchall()


class Admins:
    def __init__(self):
        cur.execute("CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, telegram_id TEXT)")
        db.commit()

    async def add_new(self, telegram_id):
        cur.execute("INSERT INTO admins (telegram_id) VALUES (%s)",
                    (telegram_id, ))
        db.commit()

    async def get_admins(self):
        cur.execute("SELECT telegram_id FROM admins")
        data = cur.fetchall()
        res = []
        for x in data:
            res.append(x[0])
        return res
