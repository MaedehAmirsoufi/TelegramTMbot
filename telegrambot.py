import logging
import sqlite3
import keyboard
from datetime import datetime, timedelta
from pytz import utc
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler, ConversationHandler
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from apscheduler.schedulers.background import BackgroundScheduler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect('tasks.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tasks
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, priority TEXT, date TEXT, status TEXT)''')
conn.commit()

def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text('Welcome to the Task Management Bot! Use /newtask to create a new task.')

def newtask(update: Update, _: CallbackContext) -> int:
    update.message.reply_text('Please send me the task title.')
    return 0  # Corresponds to expecting a title next

def receive_title(update: Update, context: CallbackContext) -> int:
    context.user_data['title'] = update.message.text
    keyboard = [[InlineKeyboardButton(text, callback_data=text.lower()) for text in ["High", "Normal", "Low"]]]
    update.message.reply_text('Select the task priority:', reply_markup=InlineKeyboardMarkup(keyboard))
    return 1  # Corresponds to expecting a priority next

def receive_priority(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    context.user_data['priority'] = query.data
    query.edit_message_text(text=f"Priority set to {context.user_data['priority']}")
    calendar, step = DetailedTelegramCalendar().build()
    query.message.reply_text(f"Select {LSTEP[step]}", reply_markup=calendar)
    return 2  # Corresponds to expecting a date next

def receive_date(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)
    if not result and key:
        query.edit_message_text(text=f"Select {LSTEP[step]}", reply_markup=key)
        return 2
    elif result:
        context.user_data['date'] = result.strftime('%Y-%m-%d')
        query.edit_message_text(text=f"Date set to {context.user_data['date']}")
        add_task_to_db(update, context)
        return -1  # End conversation

def add_task_to_db(update: Update, context: CallbackContext) -> None:
    c.execute("INSERT INTO tasks (user_id, title, priority, date, status) VALUES (?, ?, ?, ?, ?)",
              (update.effective_user.id, context.user_data['title'], context.user_data['priority'], context.user_data['date'], 'pending'))
    conn.commit()
    update.effective_message.reply_text('Task added!')

def cancel(update: Update, _: CallbackContext) -> int:
    update.message.reply_text('Task creation canceled.')
    return -1  # End conversation

def list_tasks(update: Update, _: CallbackContext) -> None:
    c.execute("SELECT id, title, priority, date, status FROM tasks WHERE user_id=?", (update.effective_user.id,))
    tasks = c.fetchall()
    if not tasks:
        update.message.reply_text("No tasks found.")
        return

    for id, title, priority, date, status in tasks:
        keyboard = [[InlineKeyboardButton("Change Priority", callback_data=f'change_priority_{id}'),
                     InlineKeyboardButton("Change Date", callback_data=f'change_date_{id}'),
                     InlineKeyboardButton("Mark as Completed", callback_data=f'mark_completed_{id}')]]
        update.message.reply_text(f"{id}. {title} - Priority: {priority}, Date: {date}, Status: {status}",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

def handle_button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    data = query.data.split('_')
    action = data[0]
    task_id = int(data[-1])  # Ensure to get the correct task ID

    if action == "change" and data[1] == "priority":
        keyboard = [
            [InlineKeyboardButton("High", callback_data=f'set_priority_high_{task_id}')],
            [InlineKeyboardButton("Normal", callback_data=f'set_priority_normal_{task_id}')],
            [InlineKeyboardButton("Low", callback_data=f'set_priority_low_{task_id}')]
        ]
        query.message.reply_text('Select new priority:', reply_markup=InlineKeyboardMarkup(keyboard))
    elif action == "change" and data[1] == "date":
        context.user_data['task_id'] = task_id
        calendar, step = DetailedTelegramCalendar().build()
        query.message.reply_text(f"Select {LSTEP[step]}", reply_markup=calendar)
    elif action == "mark" and data[1] == "completed":
        c.execute("UPDATE tasks SET status='completed' WHERE id=?", (task_id,))
        conn.commit()
        query.edit_message_text(text=f"Task {task_id} marked as completed.")
    elif action == "set" and data[1] == "priority":
        new_priority = data[2]
        c.execute("UPDATE tasks SET priority=? WHERE id=?", (new_priority, task_id))
        conn.commit()
        query.message.reply_text(f"Priority of task {task_id} set to {new_priority}.")
    elif action == "change" and data[1] == "date":
        context.user_data['task_id'] = task_id
        calendar, step = DetailedTelegramCalendar().build()
        query.message.reply_text(f"Select {LSTEP[step]}", reply_markup=calendar)
        return 2  # Continue in the conversation state expecting a date.

def set_reminder(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    c.execute("SELECT id, title FROM tasks WHERE user_id=? AND status='pending'", (user_id,))
    tasks = c.fetchall()
    
    if not tasks:
        update.message.reply_text("No pending tasks found.")
        return

    keyboard = [[InlineKeyboardButton(task[1], callback_data=f'remind_select_{task[0]}')] for task in tasks]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Select a task to set a reminder:', reply_markup=reply_markup)

def handle_reminder_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    task_id = int(query.data.split('_')[2])
    context.user_data['task_id'] = task_id

    keyboard = [
        [InlineKeyboardButton("1 Hour", callback_data='remind_1_hour')],
        [InlineKeyboardButton("5 Hours", callback_data='remind_5_hours')],
        [InlineKeyboardButton("10 Hours", callback_data='remind_10_hours')],
        [InlineKeyboardButton("1 Day", callback_data='remind_1_day')],
        [InlineKeyboardButton("3 Days", callback_data='remind_3_days')],
        [InlineKeyboardButton("10 Days", callback_data='remind_10_days')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text('Select reminder period:', reply_markup=reply_markup)

def handle_reminder_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    period, unit = query.data.replace('remind_', '').split('_')
    units = {'hour': 'hours', 'day': 'days'}  # Mapping singular to plural
    reminder_time = datetime.now() + timedelta(**{units[unit]: int(period)})
    task_id = context.user_data['task_id']
    scheduler.add_job(send_reminder, 'date', run_date=reminder_time, args=[update.effective_chat.id, update.effective_user.id, task_id])
    query.edit_message_text(text=f'Reminder set for {period} {unit}(s) from now.')

def handle_date_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)
    if not result and key:
        query.edit_message_text(text=f"Select {LSTEP[step]}", reply_markup=key)
    elif result:
        task_id = context.user_data['task_id']
        new_date = result.strftime('%Y-%m-%d')
        c.execute("UPDATE tasks SET date=? WHERE id=?", (new_date, task_id))
        conn.commit()
        query.message.reply_text(f"Date of task {task_id} set to {new_date}.")

def simple_calendar(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if 'calendar_data' not in context.user_data:
        context.user_data['calendar_data'] = {'year': 2023, 'month': 7}  # Example starting point
    year = context.user_data['calendar_data']['year']
    month = context.user_data['calendar_data']['month']

    # Generate a simple calendar layout for the given year and month
    # Update 'calendar_data' in context.user_data as needed when buttons are clicked

    # Send or edit message with the new calendar layout
    query.edit_message_text(text=f"Calendar for {month}/{year}", reply_markup=InlineKeyboardMarkup(keyboard))
    return 2

def send_reminder(chat_id: int, user_id: int, task_id: int) -> None:
    c.execute("SELECT title FROM tasks WHERE user_id=? AND id=?", (user_id, task_id))
    task = c.fetchone()
    if task:
        updater.bot.send_message(chat_id=chat_id, text=f"Reminder! Task: {task[0]}")
    else:
        updater.bot.send_message(chat_id=chat_id, text='Task not found.')

def main() -> None:
    global updater, scheduler
    updater = Updater("7299163597:AAHrtCo08atATkF-iWC7aWDCb_hgfXAEJPY", use_context=True)
    dispatcher = updater.dispatcher

    scheduler = BackgroundScheduler(timezone=utc)
    scheduler.start()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newtask', newtask)],
        states={
            0: [MessageHandler(filters.text & ~filters.command, receive_title)],
            1: [CallbackQueryHandler(receive_priority)],
            2: [CallbackQueryHandler(receive_date)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('tasks', list_tasks))
    dispatcher.add_handler(CallbackQueryHandler(handle_button, pattern='^(change|mark|set)_'))
    dispatcher.add_handler(CommandHandler('remind', set_reminder))
    dispatcher.add_handler(CallbackQueryHandler(handle_reminder_selection, pattern='^remind_select_'))
    dispatcher.add_handler(CallbackQueryHandler(handle_date_selection, pattern='^calendar-'))
    dispatcher.add_handler(CommandHandler('remind', set_reminder))
    dispatcher.add_handler(CallbackQueryHandler(handle_reminder_callback, pattern='^remind_'))
    dispatcher.add_handler(CallbackQueryHandler(handle_date_selection))



    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()