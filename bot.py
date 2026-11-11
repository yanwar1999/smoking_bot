import asyncio
import logging
import random
from datetime import datetime, date
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode

import aiosqlite
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "smoking_bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== СОСТОЯНИЯ ==================
class TestStates(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    q7 = State()
    q8 = State()
    q9 = State()

class QuitStates(StatesGroup):
    waiting_type = State()
    waiting_date = State()
    waiting_cigs = State()
    waiting_price = State()

# ================== КЛАВИАТУРЫ ==================
def main_menu():
    kb = [
        [KeyboardButton(text="🚬 Вред курения и вейпов")],
        [KeyboardButton(text="📋 Тест на зависимость")],
        [KeyboardButton(text="💪 Хочу бросить")],
        [KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="🆘 SOS")],
        [KeyboardButton(text="💬 Мотивация"), KeyboardButton(text="⚙️ Настройки")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def test_answers_kb(options: list[str]):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in options],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def type_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сигареты")],
            [KeyboardButton(text="Вейп / электронки")],
            [KeyboardButton(text="И то, и другое")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True
    )

# ================== БАЗА ДАННЫХ ==================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                quit_date TEXT,
                smoke_type TEXT DEFAULT 'cigarettes',
                cigs_per_day REAL DEFAULT 10,
                pack_price REAL DEFAULT 200,
                pack_size INTEGER DEFAULT 20,
                notifications INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        await db.commit()

async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def save_user(user_id: int, **kwargs):
    user = await get_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        if user is None:
            await db.execute(
                "INSERT INTO users (user_id, created_at) VALUES (?, ?)",
                (user_id, datetime.now().isoformat())
            )
        if kwargs:
            sets = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values()) + [user_id]
            await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", values)
        await db.commit()

# ================== ГЕЙМИФИКАЦИЯ ==================
MILESTONES = [
    (1,  "🥇 1 день", "Первый день позади."),
    (3,  "🥉 3 дня", "Уже 3 дня. Держись."),
    (7,  "🏅 Неделя", "Неделя без никотина."),
    (14, "🥈 2 недели", "Две недели. Нормально."),
    (30, "🏆 Месяц", "Месяц. Это уже серьёзно."),
    (60, "💎 2 месяца", "Два месяца. Привычка слабеет."),
    (90, "👑 3 месяца", "Три месяца. Большой результат."),
]

def get_days_free(quit_date_str: str) -> int:
    if not quit_date_str:
        return 0
    try:
        qd = date.fromisoformat(quit_date_str)
        return max(0, (date.today() - qd).days)
    except Exception:
        return 0

def get_current_milestone(days: int):
    current = None
    next_m = None
    for d, title, text in MILESTONES:
        if days >= d:
            current = (d, title, text)
        elif next_m is None:
            next_m = (d, title, text)
            break
    return current, next_m

def calc_stats(user: dict) -> dict:
    days = get_days_free(user.get("quit_date"))
    cigs_day = user.get("cigs_per_day") or 10
    price = user.get("pack_price") or 200
    pack_size = user.get("pack_size") or 20
    not_smoked = int(days * cigs_day)
    money_saved = round((not_smoked / pack_size) * price, 0)
    return {"days": days, "cigs": not_smoked, "money": int(money_saved)}

# ================== ТЕКСТЫ ==================
HARM_TEXT = """
🚬 <b>Сигареты - цифры, которые обычно не показывают</b>

Каждый год табак убивает больше 8 миллионов человек в мире. Из них около 1,3 миллиона - те, кто сам не курил, а просто дышал чужим дымом.
Источник: WHO Report on the Global Tobacco Epidemic.

В России с курением связано примерно 15% всех смертей. Это больше, чем от многих других причин, о которых говорят чаще.
Источник: Минздрав РФ, данные Росстата.

У курильщика риск рака лёгких выше в 15–30 раз по сравнению с некурящим.
Источник: IARC, US Surgeon General Report.

После инфаркта курильщики умирают чаще и восстанавливаются хуже. Никотин и окись углерода бьют по сосудам постоянно.
Источник: исследования в журнале Circulation.

Если человек курит 20 сигарет в день на протяжении 20 лет - он сильно повышает риск ХОБЛ и рака. Но даже «всего» 5–7 сигарет в день уже заметно увеличивают вероятность болезней сердца и сосудов.
Источник: European Heart Journal, meta-analyses.

Хорошая новость одна: после отказа риск начинает снижаться. Через 1 год риск болезней сердца падает почти вдвое. Через 10–15 лет риск рака лёгких снижается очень сильно.
Источник: WHO, CDC.
"""

VAPE_TEXT = """
🌫️ <b>Вейпы - что говорят исследования</b>

«Вейп безопаснее сигарет» - частичный миф. Он может быть менее вредным для тех, кто уже сильно курит и полностью перешёл на вейп. Но для некурящих и подростков это новый путь к никотиновой зависимости.
Источник: Cochrane Reviews, Public Health England, WHO.

Никотин в вейпах вызывает такую же зависимость, как в сигаретах. Мозг получает никотин быстро, особенно на высоких затяжках.
Источник: CDC, исследования в journal Nicotine & Tobacco Research.

В жидкости и аэрозоле находят формальдегид, акролеин, частицы металлов. Количество зависит от мощности устройства и жидкости.
Источник: Harvard, Johns Hopkins, FDA reports.

У подростков, которые начинали с вейпов, выше вероятность потом попробовать обычные сигареты.
Источник: мета-анализы в JAMA Pediatrics.

В 2019–2020 годах была вспышка тяжёлых поражений лёгких (EVALI), в основном связанная с жидкостями чёрного рынка и добавкой витамина E acetate.
Источник: CDC.

Вывод простой: вейп - это не «просто пар». Это доставка никотина + химия. Полностью безвредным его считать нельзя.
"""

SOS_TEXTS = [
    "Сделай несколько глубоких вдохов.",
    "Выпей воды.",
    "Встань и походи 2-3 минуты.",
    "Вспомни, зачем ты бросил.",
    "Тяга обычно проходит за 3-5 минут. Просто пережди.",
    "Отвлекись на что-то руками - телефон, мячик, что угодно.",
]

MOTIVATION_TEXTS = [
    "Сегодняшний день без никотина - уже победа.",
    "Каждый день без сигарет/вейпа делает тебя свободнее.",
    "Тяга приходит и уходит. Ты остаёшься.",
    "Ты уже дальше, чем вчера.",
    "Не надо быть идеальным. Надо просто не сдаваться сегодня.",
    "Организм начинает восстанавливаться с первого дня.",
    "Ты не один. Много людей проходят через это.",
    "Одна сигарета или тяга - не повод всё бросать. Просто продолжай.",
    "Деньги, которые не ушли на никотин, остаются у тебя.",
    "Самое сложное - в начале. Потом становится легче.",
]

# ================== ТЕСТ ==================
TEST_QUESTIONS = [
    {
        "text": "Вопрос 1/9\nСколько лет ты уже куришь или паришь?",
        "options": ["Меньше года", "1–3 года", "4–7 лет", "Больше 7 лет"],
        "scores": [1, 2, 3, 4]
    },
    {
        "text": "Вопрос 2/9\nКак часто ты это делаешь?",
        "options": ["Только иногда", "Несколько раз в неделю", "Почти каждый день", "Каждый день, много раз"],
        "scores": [0, 1, 2, 3]
    },
    {
        "text": "Вопрос 3/9\nПытался ли уже бросать?",
        "options": ["Нет, ещё не пробовал", "Пробовал 1 раз", "Пробовал несколько раз", "Много раз, но возвращался"],
        "scores": [1, 2, 3, 4]
    },
    {
        "text": "Вопрос 4/9\nЧто тебя больше всего в этом держит?",
        "options": ["Просто привычка", "Снимает стресс", "Нравится сам процесс", "Уже без этого плохо"],
        "scores": [1, 2, 3, 4]
    },
    {
        "text": "Вопрос 5/9\nНасколько сильно ты хочешь бросить прямо сейчас?",
        "options": ["Почти не хочу", "Иногда думаю об этом", "Хочу, но пока не готов", "Очень хочу"],
        "scores": [0, 1, 2, 3]
    },
    {
        "text": "Вопрос 6/9\nКак скоро после пробуждения тебе обычно хочется затянуться?",
        "options": ["В первые 5 минут", "В течение 30 минут", "В течение часа", "Могу долго обходиться"],
        "scores": [3, 2, 1, 0]
    },
    {
        "text": "Вопрос 7/9\nСогласен ли ты с фразой: «Вейп почти безвредный, это просто пар»?",
        "options": ["Полностью согласен", "Скорее согласен", "Скорее нет", "Это миф, вред есть"],
        "scores": [3, 2, 1, 0]
    },
    {
        "text": "Вопрос 8/9\nЗнаешь ли ты, что никотин в вейпах вызывает такую же зависимость, как в сигаретах?",
        "options": ["Нет, не знал", "Слышал, но сомневаюсь", "Да, знаю", "Да, и это одна из причин бросать"],
        "scores": [2, 1, 0, 0]
    },
    {
        "text": "Вопрос 9/9\nМешает ли курение/парение учёбе, работе, спорту или отношениям?",
        "options": ["Нет", "Немного", "Да, мешает", "Сильно мешает"],
        "scores": [0, 1, 2, 3]
    },
]

# ================== РОУТЕР ==================
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await save_user(message.from_user.id)
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "Бот помогает разобраться с вредом сигарет и вейпов, "
        "пройти тест и вести прогресс, если бросаешь.\n\n"
        "Выбирай в меню:",
        reply_markup=main_menu()
    )

@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu())

# ---------- ВРЕД ----------
@router.message(F.text == "🚬 Вред курения и вейпов")
async def harm_info(message: Message):
    await message.answer(HARM_TEXT, parse_mode=ParseMode.HTML)
    await message.answer(VAPE_TEXT, parse_mode=ParseMode.HTML)

# ---------- ТЕСТ ----------
@router.message(F.text == "📋 Тест на зависимость")
async def start_test(message: Message, state: FSMContext):
    await state.set_state(TestStates.q1)
    await state.update_data(score=0, q_index=0)
    q = TEST_QUESTIONS[0]
    await message.answer(q["text"], reply_markup=test_answers_kb(q["options"]))

@router.message(StateFilter(TestStates), F.text)
async def process_test(message: Message, state: FSMContext):
    data = await state.get_data()
    q_index = data.get("q_index", 0)
    score = data.get("score", 0)

    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Тест отменён.", reply_markup=main_menu())
        return

    q = TEST_QUESTIONS[q_index]
    if message.text not in q["options"]:
        await message.answer("Выбери вариант из кнопок.")
        return

    idx = q["options"].index(message.text)
    score += q["scores"][idx]
    q_index += 1

    if q_index >= len(TEST_QUESTIONS):
        await state.clear()
        # Общий уровень
        if score <= 8:
            level = "низкая"
            advice = "Пока зависимость не очень сильная. Шансы бросить хорошие."
        elif score <= 14:
            level = "средняя"
            advice = "Есть зависимость. Бросить реально, но нужен план и поддержка."
        elif score <= 20:
            level = "высокая"
            advice = "Зависимость заметная. Одних «хотелок» может не хватить - лучше действовать системно."
        else:
            level = "очень высокая"
            advice = "Сильная зависимость. Имеет смысл подключить поддержку (врач, план, окружение)."

        # Упрощённая интерпретация по шкале Фагерстрёма (по вопросу про утро)
        fagerstrom_note = ""
        # We don't have separate fagerstrom score easily, so give general scale info
        fagerstrom_note = (
            "\n\n📌 <b>Ориентир по шкале Фагерстрёма</b>\n"
            "Если тянет затянуться в первые 5–30 минут после пробуждения - это один из главных признаков никотиновой зависимости.\n"
            "Чем раньше утром хочется никотин, тем сильнее физическая зависимость."
        )

        await message.answer(
            f"📋 <b>Результат</b>\n\n"
            f"Баллы: <b>{score}</b>\n"
            f"Уровень зависимости: <b>{level}</b>\n\n"
            f"{advice}"
            f"{fagerstrom_note}\n\n"
            f"Если решишь бросать - жми «💪 Хочу бросить».",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu()
        )
        return

    await state.update_data(score=score, q_index=q_index)
    next_states = [TestStates.q1, TestStates.q2, TestStates.q3, TestStates.q4, TestStates.q5, TestStates.q6, TestStates.q7, TestStates.q8, TestStates.q9]
    await state.set_state(next_states[q_index])
    nq = TEST_QUESTIONS[q_index]
    await message.answer(nq["text"], reply_markup=test_answers_kb(nq["options"]))

# ---------- ХОЧУ БРОСИТЬ ----------
@router.message(F.text == "💪 Хочу бросить")
async def start_quit(message: Message, state: FSMContext):
    await state.set_state(QuitStates.waiting_type)
    await message.answer(
        "Что именно бросаешь?",
        reply_markup=type_kb()
    )

@router.message(QuitStates.waiting_type)
async def process_type(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return

    mapping = {
        "Сигареты": "cigarettes",
        "Вейп / электронки": "vape",
        "И то, и другое": "both"
    }
    if message.text not in mapping:
        await message.answer("Выбери один из вариантов на кнопках.")
        return

    await state.update_data(smoke_type=mapping[message.text])
    await state.set_state(QuitStates.waiting_date)
    await message.answer(
        "С какой даты считаем отказ?\n"
        "Напиши дату в формате ДД.ММ.ГГГГ или слово «сегодня».",
        reply_markup=cancel_kb()
    )

@router.message(QuitStates.waiting_date)
async def process_quit_date(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    if text == "❌ отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return

    if text in ("сегодня", "today"):
        quit_date = date.today()
    else:
        try:
            quit_date = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await message.answer("Напиши дату как ДД.ММ.ГГГГ или «сегодня».")
            return

    await state.update_data(quit_date=quit_date.isoformat())
    await state.set_state(QuitStates.waiting_cigs)
    await message.answer(
        "Сколько примерно раз в день курил/парил?\n"
        "Напиши число (например 10)."
    )

@router.message(QuitStates.waiting_cigs)
async def process_cigs(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return
    try:
        cigs = float(message.text.replace(",", "."))
        if cigs <= 0 or cigs > 100:
            raise ValueError
    except ValueError:
        await message.answer("Напиши нормальное число, например 10.")
        return

    await state.update_data(cigs_per_day=cigs)
    await state.set_state(QuitStates.waiting_price)
    await message.answer(
        "Сколько примерно тратил в день на сигареты/жидкость (в рублях)?\n"
        "Напиши число."
    )

@router.message(QuitStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return
    try:
        price = float(message.text.replace(",", "."))
        if price < 0 or price > 5000:
            raise ValueError
    except ValueError:
        await message.answer("Напиши сумму числом.")
        return

    data = await state.get_data()
    await save_user(
        message.from_user.id,
        quit_date=data["quit_date"],
        smoke_type=data.get("smoke_type", "cigarettes"),
        cigs_per_day=data["cigs_per_day"],
        pack_price=price,
        pack_size=1  # теперь считаем через дневные траты
    )
    await state.clear()

    days = get_days_free(data["quit_date"])
    type_text = {
        "cigarettes": "сигареты",
        "vape": "вейп",
        "both": "сигареты и вейп"
    }.get(data.get("smoke_type"), "никотин")

    await message.answer(
        f"Готово.\n\n"
        f"Бросаешь: <b>{type_text}</b>\n"
        f"Дата отказа: <b>{date.fromisoformat(data['quit_date']).strftime('%d.%m.%Y')}</b>\n"
        f"Дней сейчас: <b>{days}</b>\n\n"
        f"Прогресс смотри в «📊 Мой прогресс».",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu()
    )

# ---------- ПРОГРЕСС ----------
@router.message(F.text == "📊 Мой прогресс")
async def show_progress(message: Message):
    user = await get_user(message.from_user.id)
    if not user or not user.get("quit_date"):
        await message.answer(
            "Сначала укажи дату отказа через «💪 Хочу бросить».",
            reply_markup=main_menu()
        )
        return

    stats = calc_stats(user)
    days = stats["days"]
    current, next_m = get_current_milestone(days)

    # Пересчёт денег через дневные траты
    daily_spend = user.get("pack_price") or 0
    money = int(days * daily_spend)

    type_text = {
        "cigarettes": "сигареты",
        "vape": "вейп",
        "both": "сигареты + вейп"
    }.get(user.get("smoke_type"), "никотин")

    text = (
        f"📊 <b>Прогресс</b>\n\n"
        f"Бросаешь: {type_text}\n"
        f"Дней без: <b>{days}</b>\n"
        f"Сэкономлено примерно: <b>{money} ₽</b>\n"
    )

    if current:
        text += f"\nДостижение: <b>{current[1]}</b>\n{current[2]}"

    if next_m:
        left = next_m[0] - days
        text += f"\n\nДо «{next_m[1]}» осталось {left} дн."

    if days >= 90:
        text += "\n\n3 месяца позади. Хороший результат."

    await message.answer(text, parse_mode=ParseMode.HTML)

# ---------- SOS ----------
@router.message(F.text == "🆘 SOS")
async def sos_handler(message: Message):
    tip = random.choice(SOS_TEXTS)
    await message.answer(f"🆘\n\n{tip}\n\nОбычно быстро отпускает.")

# ---------- МОТИВАЦИЯ ----------
@router.message(F.text == "💬 Мотивация")
async def motivation_handler(message: Message):
    text = random.choice(MOTIVATION_TEXTS)
    await message.answer(f"💬\n\n{text}")

# ---------- НАСТРОЙКИ ----------
@router.message(F.text == "⚙️ Настройки")
async def settings_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user or not user.get("quit_date"):
        await message.answer("Данные ещё не заполнены.\nСначала нажми «💪 Хочу бросить».")
        return

    type_text = {
        "cigarettes": "сигареты",
        "vape": "вейп",
        "both": "сигареты + вейп"
    }.get(user.get("smoke_type"), "не указано")

    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"Тип: {type_text}\n"
        f"Дата отказа: {date.fromisoformat(user['quit_date']).strftime('%d.%m.%Y')}\n"
        f"Примерно раз в день: {user.get('cigs_per_day', '-')}\n"
        f"Траты в день: {user.get('pack_price', '-')} ₽\n\n"
        f"Чтобы изменить - снова нажми «💪 Хочу бросить»."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message()
async def fallback(message: Message):
    await message.answer("Выбери действие из меню.", reply_markup=main_menu())

# ================== ЗАПУСК ==================
async def main():
    if not BOT_TOKEN:
        print("Нет BOT_TOKEN в .env")
        return

    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
