from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.formatters import format_reminder_datetime


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Memory", callback_data="menu:memory"),
                InlineKeyboardButton("Reminders", callback_data="menu:reminders"),
            ],
            [
                InlineKeyboardButton("Study", callback_data="menu:study"),
                InlineKeyboardButton("Future Me", callback_data="menu:future_me"),
            ],
            [
                InlineKeyboardButton("Daily Summary", callback_data="menu:summary"),
                InlineKeyboardButton("Help", callback_data="menu:help"),
            ],
        ]
    )


def memory_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Save Memory", callback_data="memory:save"),
                InlineKeyboardButton("View Memories", callback_data="memory:list"),
            ],
            [
                InlineKeyboardButton("Search Memories", callback_data="memory:search"),
                InlineKeyboardButton("Delete Memory", callback_data="memory:delete_menu"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )


def reminder_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Create Reminder", callback_data="reminder:create"),
                InlineKeyboardButton("View Reminders", callback_data="reminder:list"),
            ],
            [
                InlineKeyboardButton("Cancel Reminder", callback_data="reminder:cancel_menu"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )

def study_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Create Study Plan", callback_data="study:create"),
                InlineKeyboardButton("View Study Plans", callback_data="study:list"),
            ],
            [
                InlineKeyboardButton("View Study Tasks", callback_data="study:tasks"),
                InlineKeyboardButton("Cancel Study Plan", callback_data="study:cancel_menu"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )

def reminder_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("In 15 min", callback_data="reminder_time:in_15"),
                InlineKeyboardButton("In 30 min", callback_data="reminder_time:in_30"),
            ],
            [
                InlineKeyboardButton("In 1 hour", callback_data="reminder_time:in_60"),
                InlineKeyboardButton("In 2 hours", callback_data="reminder_time:in_120"),
            ],
            [
                InlineKeyboardButton("Today 8 PM", callback_data="reminder_time:today_20"),
            ],
            [
                InlineKeyboardButton("Tomorrow 9 AM", callback_data="reminder_time:tomorrow_09"),
                InlineKeyboardButton("Tomorrow 8 PM", callback_data="reminder_time:tomorrow_20"),
            ],
            [
                InlineKeyboardButton("Pick Date/Time", callback_data="reminder_time:pick"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def reminder_day_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Today", callback_data="reminder_day:today"),
                InlineKeyboardButton("Tomorrow", callback_data="reminder_day:tomorrow"),
            ],
            [
                InlineKeyboardButton("In 2 days", callback_data="reminder_day:in_2_days"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="reminder:back_to_time"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def reminder_hour_keyboard() -> InlineKeyboardMarkup:
    rows = []

    hours = list(range(8, 23))
    for i in range(0, len(hours), 3):
        row = [
            InlineKeyboardButton(
                f"{hour:02d}:00",
                callback_data=f"reminder_hour:{hour}",
            )
            for hour in hours[i:i + 3]
        ]
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton("Back", callback_data="reminder_time:pick"),
            InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
        ]
    )

    return InlineKeyboardMarkup(rows)


def reminder_minute_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(":00", callback_data="reminder_minute:00"),
                InlineKeyboardButton(":15", callback_data="reminder_minute:15"),
            ],
            [
                InlineKeyboardButton(":30", callback_data="reminder_minute:30"),
                InlineKeyboardButton(":45", callback_data="reminder_minute:45"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="reminder_day:back_to_hour"),
                InlineKeyboardButton("Cancel", callback_data="flow:cancel"),
            ],
        ]
    )


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Main Menu", callback_data="menu:main")]
        ]
    )


def back_to_memory_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Memory Menu", callback_data="menu:memory")]
        ]
    )


def back_to_reminders_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Reminder Menu", callback_data="menu:reminders")]
        ]
    )


def back_to_study_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Study Menu", callback_data="menu:study")]
        ]
    )

def delete_memory_keyboard(memories: list[dict]) -> InlineKeyboardMarkup:
    rows = []

    for memory in memories:
        memory_id = memory.get("id")
        content = memory.get("content", "")

        label = f"Delete: {content[:35]}"
        if len(content) > 35:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"memory_delete:{memory_id}")]
        )

    rows.append([InlineKeyboardButton("Back", callback_data="menu:memory")])

    return InlineKeyboardMarkup(rows)


def cancel_reminder_keyboard(reminders: list[dict]) -> InlineKeyboardMarkup:
    rows = []

    for reminder in reminders:
        reminder_id = reminder.get("id")
        message = reminder.get("message", "")
        scheduled_time = format_reminder_datetime(reminder.get("scheduled_time", ""))

        label = f"Cancel: {scheduled_time} — {message[:25]}"
        if len(message) > 25:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"reminder_cancel:{reminder_id}")]
        )

    rows.append([InlineKeyboardButton("Back", callback_data="menu:reminders")])

    return InlineKeyboardMarkup(rows)

def complete_study_task_keyboard(tasks: list[dict]) -> InlineKeyboardMarkup:
    rows = []

    pending_tasks = [
        task for task in tasks
        if task.get("status") == "pending"
    ]

    for task in pending_tasks[:10]:
        task_id = task.get("id")
        day_number = task.get("day_number")
        title = task.get("title", "")

        label = f"Complete Day {day_number}: {title[:25]}"
        if len(title) > 25:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"study_complete:{task_id}")]
        )

    rows.append([InlineKeyboardButton("Study Menu", callback_data="menu:study")])

    return InlineKeyboardMarkup(rows)

def cancel_study_plan_keyboard(study_plans: list[dict]) -> InlineKeyboardMarkup:
    rows = []

    for plan in study_plans:
        plan_id = plan.get("id")
        topic = plan.get("topic", "")

        label = f"Cancel: {topic[:35]}"
        if len(topic) > 35:
            label += "..."

        rows.append(
            [InlineKeyboardButton(label, callback_data=f"study_cancel:{plan_id}")]
        )

    rows.append([InlineKeyboardButton("Study Menu", callback_data="menu:study")])

    return InlineKeyboardMarkup(rows)

def study_reminder_prompt_keyboard(study_plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Yes, remind me",
                    callback_data=f"study_reminder_yes:{study_plan_id}",
                ),
                InlineKeyboardButton(
                    "No",
                    callback_data="study_reminder_no",
                ),
            ],
            [
                InlineKeyboardButton("Study Menu", callback_data="menu:study"),
            ],
        ]
    )


def study_reminder_time_keyboard(study_plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "9 AM",
                    callback_data=f"study_reminder_time:{study_plan_id}:9:0",
                ),
                InlineKeyboardButton(
                    "6 PM",
                    callback_data=f"study_reminder_time:{study_plan_id}:18:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    "8 PM",
                    callback_data=f"study_reminder_time:{study_plan_id}:20:0",
                ),
                InlineKeyboardButton(
                    "No reminders",
                    callback_data="study_reminder_no",
                ),
            ],
            [
                InlineKeyboardButton("Study Menu", callback_data="menu:study"),
            ],
        ]
    )