 # Task Manager Bot

Task Manager Bot is a Telegram bot that helps users manage their tasks efficiently. Users can create, list, and update tasks, as well as set reminders for their tasks.

## Features

- Create new tasks with a title, priority, and due date.
- List all tasks with options to change priority, date, or mark as completed.
- Set reminders for tasks.
- Use an inline keyboard for easy interaction.

## Prerequisites

- Python 3.9+
- Telegram Bot API token
- SQLite3

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/task-manager-bot.git
    cd task-manager-bot
    ```

2. Create and activate a virtual environment:
    ```sh
    python -m venv myenv
    myenv\Scripts\activate  # On Windows
    ```

3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Setup

1. Create a new bot on Telegram and get the API token. Replace the placeholder token in `main()` with your bot's token:
    ```python
    updater = Updater("YOUR_TELEGRAM_BOT_API_TOKEN", use_context=True)
    ```

2. Create the SQLite database:
    ```sh
    python -c "import sqlite3; conn = sqlite3.connect('tasks.db'); c = conn.cursor(); c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, priority TEXT, date TEXT, status TEXT)'''); conn.commit(); conn.close()"
    ```

## Usage

1. Start the bot:
    ```sh
    python telegrambot.py
    ```

2. Interact with the bot on Telegram:
    - Use `/start` to initialize the bot.
    - Use `/newtask` to create a new task.
    - Use `/tasks` to list all tasks.
    - Use `/remind` to set reminders for tasks.




