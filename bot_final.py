"""
БОТ ДЛЯ БАНЬ - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПОИСКОМ ПО АДРЕСУ
"""
import asyncio
import sqlite3
import os
import time
import hashlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InputMediaPhoto

# Устанавливаем Pillow если не установлен
try:
    from PIL import Image
    print("✅ Pillow установлен")
except ImportError:
    print("⚠️ Pillow не установлен. Устанавливаем...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'Pillow'])
    from PIL import Image
    print("✅ Pillow установлен")

# Устанавливаем geopy для геокодирования
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import distance
    print("✅ Geopy установлен")
except ImportError:
    print("⚠️ Geopy не установлен. Устанавливаем...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'geopy'])
    from geopy.geocoders import Nominatim
    from geopy.distance import distance
    print("✅ Geopy установлен")

# Токен бота
BOT_TOKEN = "8363344834:AAH-uwrnrI-46P8mT0cfBHZAtka0xgx2x7g"

# Пароль для админки
ADMIN_PASSWORD = "admin123"

# ID администратора
ADMIN_ID = 7768521585

# Создаем бота и диспетчер
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Настройка путей для фото
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE_DIR, "bathhouse_photos")

# Создаем папку для фото
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)
    print(f"✅ Создана папка для фото: {PHOTOS_DIR}")

# Инициализация геокодера
geolocator = Nominatim(user_agent="bathhouse_bot")

# ========== БАЗА ДАННЫХ ==========
def get_db_connection():
    """Создать соединение с БД"""
    conn = sqlite3.connect('bathhouses.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Создаем основную таблицу бань
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bathhouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        price INTEGER NOT NULL,
        guests INTEGER NOT NULL,
        contact TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Создаем таблицу для фотографий
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bathhouse_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bathhouse_id INTEGER NOT NULL,
        photo_path TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bathhouse_id) REFERENCES bathhouses (id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

init_database()

# ========== ФУНКЦИИ РАБОТЫ С БД ==========
def get_bathhouses_from_db():
    """Получить все бани из БД"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bathhouses ORDER BY id DESC")
    bath_rows = cursor.fetchall()
    
    result = []
    for bath_row in bath_rows:
        bath = dict(bath_row)
        
        # Получаем фотографии для этой бани
        cursor.execute('''
            SELECT photo_path FROM bathhouse_photos 
            WHERE bathhouse_id = ? 
            ORDER BY sort_order ASC, id ASC
        ''', (bath['id'],))
        
        photo_rows = cursor.fetchall()
        photos = [row['photo_path'] for row in photo_rows]
        
        # Убираем дубликаты
        unique_photos = []
        seen = set()
        for photo in photos:
            if photo not in seen:
                seen.add(photo)
                unique_photos.append(photo)
        
        bath['photos'] = unique_photos
        bath['photo_path'] = unique_photos[0] if unique_photos else ""
        
        result.append(bath)
    
    conn.close()
    return result

def get_bathhouse_by_id(bath_id):
    """Получить баню по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bathhouses WHERE id = ?", (bath_id,))
    bath_row = cursor.fetchone()
    
    if not bath_row:
        conn.close()
        return None
    
    bath = dict(bath_row)
    
    # Получаем фотографии
    cursor.execute('''
        SELECT photo_path FROM bathhouse_photos 
        WHERE bathhouse_id = ? 
        ORDER BY sort_order ASC, id ASC
    ''', (bath_id,))
    
    photo_rows = cursor.fetchall()
    photos = [row['photo_path'] for row in photo_rows]
    
    # Убираем дубликаты
    unique_photos = []
    seen = set()
    for photo in photos:
        if photo not in seen:
            seen.add(photo)
            unique_photos.append(photo)
    
    bath['photos'] = unique_photos
    bath['photo_path'] = unique_photos[0] if unique_photos else ""
    
    conn.close()
    return bath

def save_bathhouse_to_db(data):
    """Сохранить баню в БД"""
    required_fields = ['name', 'address', 'price', 'guests', 'contact']
    for field in required_fields:
        if field not in data or not data[field]:
            print(f"❌ Ошибка: отсутствует поле {field}")
            return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO bathhouses (name, address, price, guests, contact, description)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['address'],
            int(data['price']),
            int(data['guests']),
            data['contact'],
            data.get('description', '')
        ))
        
        bath_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Баня сохранена с ID: {bath_id}")
        return bath_id
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def add_bathhouse_photo(bath_id, photo_path):
    """Добавить фото к бане"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO bathhouse_photos (bathhouse_id, photo_path)
            VALUES (?, ?)
        ''', (bath_id, photo_path))
        
        conn.commit()
        print(f"✅ Фото добавлено к бане {bath_id}: {os.path.basename(photo_path)}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def delete_bathhouse_from_db(bath_id):
    """Удалить баню"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Получаем пути к фото для удаления файлов
        cursor.execute("SELECT photo_path FROM bathhouse_photos WHERE bathhouse_id = ?", (bath_id,))
        photos = cursor.fetchall()
        
        # Удаляем файлы
        for photo in photos:
            photo_path = photo['photo_path']
            if os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                    print(f"✅ Удален файл: {photo_path}")
                except:
                    pass
        
        # Удаляем запись из БД
        cursor.execute("DELETE FROM bathhouses WHERE id = ?", (bath_id,))
        conn.commit()
        print(f"✅ Баня {bath_id} удалена")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_bathhouse_in_db(bath_id, data):
    """Обновить данные бани"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        UPDATE bathhouses 
        SET name = ?, address = ?, price = ?, guests = ?, contact = ?, description = ?
        WHERE id = ?
        ''', (
            data['name'],
            data['address'],
            int(data['price']),
            int(data['guests']),
            data['contact'],
            data.get('description', ''),
            bath_id
        ))
        
        conn.commit()
        print(f"✅ Баня {bath_id} обновлена")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ========== ФУНКЦИИ ДЛЯ КНОПОК ==========
def get_contact_button(contact):
    """Создать кнопку для Telegram ссылок"""
    if contact.startswith('@'):
        username = contact[1:]
        return InlineKeyboardButton(
            text="💬 Перейти в Telegram", 
            url=f"https://t.me/{username}"
        )
    elif 't.me/' in contact:
        return InlineKeyboardButton(
            text="💬 Перейти в Telegram", 
            url=contact
        )
    return None

# ========== ФУНКЦИЯ ДЛЯ КОНВЕРТАЦИИ ФОТО ==========
def convert_image_to_jpg(image_path):
    """Конвертирует изображение в JPG формат и возвращает новый путь"""
    try:
        # Проверяем существует ли файл
        if not os.path.exists(image_path):
            print(f"❌ Файл не существует: {image_path}")
            return None
            
        # Открываем изображение
        img = Image.open(image_path)
        print(f"🖼️ Исходное изображение: формат {img.format}, режим {img.mode}, размер {img.size}")
        
        # Конвертируем в RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            # Создаем белый фон
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            # Вставляем изображение с учетом альфа-канала
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[3])
            elif img.mode == 'LA':
                rgb_img.paste(img, mask=img.split()[1])
            else:  # P режим (палитра)
                if img.info.get('transparency'):
                    rgb_img.paste(img, mask=img.convert('RGBA').split()[3])
                else:
                    rgb_img.paste(img)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Создаем новый путь с уникальным именем
        base_name = os.path.splitext(image_path)[0]
        new_path = f"{base_name}_converted_{int(time.time())}.jpg"
        
        # Сохраняем как JPG с оптимизацией
        img.save(new_path, 'JPEG', quality=85, optimize=True)
        
        # Проверяем размер нового файла
        if os.path.exists(new_path):
            new_size = os.path.getsize(new_path)
            print(f"✅ Конвертация успешна: {new_path} ({new_size} байт)")
            return new_path
        else:
            print(f"❌ Файл не создан после конвертации")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка конвертации: {e}")
        import traceback
        traceback.print_exc()
        return None

# ========== ФУНКЦИЯ ДЛЯ СОХРАНЕНИЯ ФОТО ==========
async def save_photo_file(file, bath_id, index=0):
    """Сохраняет фото в JPG формате, предотвращая дубликаты"""
    
    # Создаем временный файл
    temp_filename = f"temp_{bath_id}_{int(time.time())}_{index}.jpg"
    temp_path = os.path.join(PHOTOS_DIR, temp_filename)
    
    # Скачиваем файл
    await bot.download_file(file.file_path, temp_path)
    
    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
        try:
            # Открываем изображение
            img = Image.open(temp_path)
            
            # Конвертируем в RGB
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    rgb_img.paste(img, mask=img.split()[3])
                elif img.mode == 'LA':
                    rgb_img.paste(img, mask=img.split()[1])
                else:
                    rgb_img.paste(img)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Создаем уникальное имя на основе содержимого файла
            # Это предотвратит сохранение дубликатов
            with open(temp_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            
            final_path = os.path.join(PHOTOS_DIR, f"{bath_id}_{file_hash}_{index}.jpg")
            
            # Сохраняем с хорошим качеством
            img.save(final_path, 'JPEG', quality=95, optimize=True)
            
            # Удаляем временный файл
            try:
                os.remove(temp_path)
            except:
                pass
            
            print(f"✅ Фото сохранено: {final_path}")
            return final_path
        except Exception as e:
            print(f"❌ Ошибка при конвертации: {e}")
            return temp_path
    
    return None

# ========== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ФОТО ==========
async def check_and_fix_photos():
    """Проверяет все фото и конвертирует проблемные"""
    print("🔍 Проверка фотографий...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, photo_path FROM bathhouse_photos")
    photos = cursor.fetchall()
    
    converted_count = 0
    deleted_count = 0
    
    for photo in photos:
        photo_id = photo['id']
        photo_path = photo['photo_path']
        
        if not os.path.exists(photo_path):
            print(f"❌ Фото {photo_id} не найдено: {photo_path}")
            cursor.execute("DELETE FROM bathhouse_photos WHERE id = ?", (photo_id,))
            deleted_count += 1
            continue
        
        # Проверяем размер файла
        file_size = os.path.getsize(photo_path)
        if file_size < 1000:  # Меньше 1KB - удаляем
            print(f"❌ Фото {photo_id} слишком маленькое: {file_size} байт")
            try:
                os.remove(photo_path)
            except:
                pass
            cursor.execute("DELETE FROM bathhouse_photos WHERE id = ?", (photo_id,))
            deleted_count += 1
            continue
        
        # Проверяем расширение
        ext = os.path.splitext(photo_path)[1].lower()
        if ext not in ['.jpg', '.jpeg']:
            print(f"⚠️ Фото {photo_id} имеет формат {ext}, конвертируем в JPG")
            new_path = convert_image_to_jpg(photo_path)
            if new_path and os.path.exists(new_path):
                # Обновляем путь в БД
                cursor.execute("UPDATE bathhouse_photos SET photo_path = ? WHERE id = ?", (new_path, photo_id))
                converted_count += 1
                print(f"✅ Фото {photo_id} сконвертировано")
            else:
                print(f"❌ Не удалось сконвертировать фото {photo_id}")
                cursor.execute("DELETE FROM bathhouse_photos WHERE id = ?", (photo_id,))
                deleted_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Проверка завершена. Сконвертировано: {converted_count}, Удалено: {deleted_count}")

# ========== ГЕОКОДИНГ И ПОИСК ПО АДРЕСУ ==========
def geocode_address(address):
    """Преобразует адрес в координаты"""
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return (location.latitude, location.longitude)
        return None
    except Exception as e:
        print(f"❌ Ошибка геокодирования: {e}")
        return None

def calculate_distance(coord1, coord2):
    """Рассчитывает расстояние между двумя координатами в км"""
    return distance(coord1, coord2).km

# ========== ОТПРАВКА КАРТОЧКИ ==========
async def send_bathhouse_card(message_or_chat_id, bath):
    """Отправить карточку бани с фото в хорошем качестве"""
    
    if isinstance(message_or_chat_id, Message):
        chat_id = message_or_chat_id.chat.id
    else:
        chat_id = message_or_chat_id
    
    # Текст карточки
    text = f"<b>🏠 {bath['name']}</b>\n\n"
    text += f"📍 <b>Адрес:</b> {bath['address']}\n"
    text += f"👥 <b>Гости:</b> до {bath['guests']} человек\n"
    text += f"💰 <b>Цена:</b> {bath['price']} руб/час\n"
    
    if bath['description']:
        text += f"📝 <b>Описание:</b> {bath['description'][:200]}\n"
    
    # Контакт
    if bath['contact'].startswith('@'):
        text += f"\n💬 <b>Telegram:</b> {bath['contact']}"
    elif bath['contact'].startswith('+'):
        text += f"\n📞 <b>Телефон:</b> {bath['contact']}"
    else:
        text += f"\n📞 <b>Контакт:</b> {bath['contact']}"
    
    # Клавиатура для Telegram
    keyboard = None
    contact_button = get_contact_button(bath['contact'])
    if contact_button:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[contact_button]])
    
    # Получаем уникальные фото
    photos = bath.get('photos', [])
    unique_photos = []
    seen = set()
    
    for photo_path in photos:
        if photo_path not in seen:
            seen.add(photo_path)
            if os.path.exists(photo_path):
                file_size = os.path.getsize(photo_path)
                if 1000 < file_size < 10 * 1024 * 1024:
                    unique_photos.append(photo_path)
                    print(f"✅ Фото готово: {os.path.basename(photo_path)} ({file_size} байт)")
    
    if unique_photos:
        # Сначала отправляем текст
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Затем отправляем все фото по одному
        for i, photo_path in enumerate(unique_photos, 1):
            try:
                photo = FSInputFile(photo_path)
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=f"📸 Фото {i} из {len(unique_photos)}" if len(unique_photos) > 1 else None
                )
                print(f"✅ Отправлено фото {i}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Ошибка при отправке фото {i}: {e}")
    else:
        # Если нет фото, отправляем только текст
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

# ========== СОСТОЯНИЯ ==========
class AdminStates(StatesGroup):
    waiting_for_password = State()
    admin_menu = State()
    adding_photo = State()

class AddBathStates(StatesGroup):
    name = State()
    address = State()
    price = State()
    guests = State()
    contact = State()
    description = State()
    photos = State()

class EditBathStates(StatesGroup):
    selecting = State()
    editing = State()
    deleting = State()

class SearchStates(StatesGroup):
    budget = State()
    guests = State()
    address = State()  # Новое состояние для поиска по адресу

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти баню")],
            [KeyboardButton(text="🏠 Все бани"), KeyboardButton(text="💰 По бюджету")],
            [KeyboardButton(text="👥 По гостям"), KeyboardButton(text="📍 Поиск по адресу")],
            [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📞 Контакты")]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все бани"), KeyboardButton(text="➕ Добавить баню")],
            [KeyboardButton(text="📸 Управление фото"), KeyboardButton(text="✏️ Редактировать/Удалить")],
            [KeyboardButton(text="🔙 Выход из админки")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

def get_photo_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Готово")]
        ],
        resize_keyboard=True
    )

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Привет! Я бот для поиска бань!</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа")
        return
    
    await state.set_state(AdminStates.waiting_for_password)
    await message.answer(
        "🔐 Введите пароль:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 На главную")]],
            resize_keyboard=True
        )
    )

@dp.message(AdminStates.waiting_for_password)
async def check_password(message: Message, state: FSMContext):
    if message.text == "🔙 На главную":
        await state.clear()
        await message.answer("Главное меню", reply_markup=get_main_keyboard())
        return
    
    if message.text == ADMIN_PASSWORD:
        await state.set_state(AdminStates.admin_menu)
        await message.answer(
            "👑 Админ-панель",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Неверный пароль")

# ========== АДМИН-ПАНЕЛЬ ==========
@dp.message(AdminStates.admin_menu, F.text == "📋 Все бани")
async def admin_show_all(message: Message, state: FSMContext):
    baths = get_bathhouses_from_db()
    
    if not baths:
        await message.answer("Нет бань", reply_markup=get_admin_keyboard())
        return
    
    await message.answer(f"Найдено бань: {len(baths)}", reply_markup=get_admin_keyboard())
    
    for bath in baths:
        await send_bathhouse_card(message, bath)
        await asyncio.sleep(1)

@dp.message(AdminStates.admin_menu, F.text == "➕ Добавить баню")
async def add_bath_start(message: Message, state: FSMContext):
    await state.set_state(AddBathStates.name)
    await message.answer(
        "Введите название бани:",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(AddBathStates.name)
async def add_bath_name(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(name=message.text)
    await state.set_state(AddBathStates.address)
    await message.answer("Введите адрес:")

@dp.message(AddBathStates.address)
async def add_bath_address(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(address=message.text)
    await state.set_state(AddBathStates.price)
    await message.answer("Введите цену за час (руб):")

@dp.message(AddBathStates.price)
async def add_bath_price(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    
    await state.update_data(price=int(message.text))
    await state.set_state(AddBathStates.guests)
    await message.answer("Введите макс. количество гостей:")

@dp.message(AddBathStates.guests)
async def add_bath_guests(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    if not message.text.isdigit():
        await message.answer("Введите число!")
        return
    
    await state.update_data(guests=int(message.text))
    await state.set_state(AddBathStates.contact)
    await message.answer("Введите контакт (@username или телефон):")

@dp.message(AddBathStates.contact)
async def add_bath_contact(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(contact=message.text)
    await state.set_state(AddBathStates.description)
    await message.answer("Введите описание (или отправьте 'пропустить'):")

@dp.message(AddBathStates.description)
async def add_bath_description(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())
        return
    
    if message.text.lower() != "пропустить":
        await state.update_data(description=message.text)
    
    data = await state.get_data()
    bath_id = save_bathhouse_to_db(data)
    
    if bath_id:
        await state.update_data(bath_id=bath_id, photos_added=[])
        await state.set_state(AddBathStates.photos)
        await message.answer(
            "✅ Баня создана! Теперь отправьте фото (можно несколько).\n"
            "Когда закончите, нажмите '✅ Готово'",
            reply_markup=get_photo_keyboard()
        )
    else:
        await state.set_state(AdminStates.admin_menu)
        await message.answer("❌ Ошибка", reply_markup=get_admin_keyboard())

@dp.message(AddBathStates.photos, F.photo)
async def add_bath_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    bath_id = data['bath_id']
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    # Сохраняем фото
    photos_added = data.get('photos_added', [])
    file_path = await save_photo_file(file, bath_id, len(photos_added))
    
    if file_path and os.path.exists(file_path):
        if add_bathhouse_photo(bath_id, file_path):
            photos_added.append(file_path)
            await state.update_data(photos_added=photos_added)
            await message.answer(f"✅ Фото {len(photos_added)} добавлено!")
    else:
        await message.answer("❌ Ошибка при сохранении фото")

@dp.message(AddBathStates.photos, F.text == "✅ Готово")
async def finish_add_bath(message: Message, state: FSMContext):
    data = await state.get_data()
    photos_count = len(data.get('photos_added', []))
    
    await state.set_state(AdminStates.admin_menu)
    await message.answer(
        f"✅ Баня полностью добавлена! Добавлено фото: {photos_count}",
        reply_markup=get_admin_keyboard()
    )

# ========== УПРАВЛЕНИЕ ФОТО ==========
@dp.message(AdminStates.admin_menu, F.text == "📸 Управление фото")
async def manage_photos_start(message: Message, state: FSMContext):
    baths = get_bathhouses_from_db()
    
    if not baths:
        await message.answer("Нет бань", reply_markup=get_admin_keyboard())
        return
    
    builder = InlineKeyboardBuilder()
    for bath in baths:
        photo_count = len(bath.get('photos', []))
        builder.button(
            text=f"{bath['id']} - {bath['name']} ({photo_count} фото)",
            callback_data=f"manage_{bath['id']}"
        )
    
    builder.button(text="🔙 Назад", callback_data="back_admin")
    builder.adjust(1)
    
    await message.answer(
        "Выберите баню:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("manage_"))
async def manage_photos_menu(callback: CallbackQuery, state: FSMContext):
    bath_id = int(callback.data.split("_")[1])
    bath = get_bathhouse_by_id(bath_id)
    
    if not bath:
        await callback.answer("Ошибка")
        return
    
    photos = bath.get('photos', [])
    text = f"Баня: {bath['name']}\nФото: {len(photos)}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📷 Добавить фото", callback_data=f"addphoto_{bath_id}")
    builder.button(text="🔙 Назад", callback_data="back_photos")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("addphoto_"))
async def add_photo_start(callback: CallbackQuery, state: FSMContext):
    bath_id = int(callback.data.split("_")[1])
    await state.update_data(addphoto_bath_id=bath_id)
    await state.set_state(AdminStates.adding_photo)
    
    await callback.message.answer(
        "Отправьте фото:",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@dp.message(AdminStates.adding_photo, F.photo)
async def add_photo_process(message: Message, state: FSMContext):
    data = await state.get_data()
    bath_id = data['addphoto_bath_id']
    
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    
    # Сохраняем фото
    file_path = await save_photo_file(file, bath_id)
    
    if file_path and os.path.exists(file_path):
        if add_bathhouse_photo(bath_id, file_path):
            await state.set_state(AdminStates.admin_menu)
            await message.answer(
                "✅ Фото добавлено!",
                reply_markup=get_admin_keyboard()
            )
    else:
        await message.answer("❌ Ошибка при сохранении фото")

@dp.message(AdminStates.adding_photo)
async def add_photo_cancel(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Отменено", reply_markup=get_admin_keyboard())

# ========== РЕДАКТИРОВАНИЕ/УДАЛЕНИЕ (ИСПРАВЛЕННАЯ ВЕРСИЯ) ==========

@dp.message(AdminStates.admin_menu, F.text == "✏️ Редактировать/Удалить")
async def edit_delete_start(message: Message, state: FSMContext):
    baths = get_bathhouses_from_db()
    
    if not baths:
        await message.answer("Нет бань", reply_markup=get_admin_keyboard())
        return
    
    builder = InlineKeyboardBuilder()
    for bath in baths:
        # Добавляем информацию о количестве фото
        photo_count = len(bath.get('photos', []))
        builder.button(
            text=f"🏠 {bath['id']} - {bath['name']} ({photo_count} фото)",
            callback_data=f"edit_select_{bath['id']}"
        )
    
    builder.button(text="🔙 Назад", callback_data="back_to_admin_main")
    builder.adjust(1)
    
    await message.answer(
        "✏️ <b>Выберите баню для редактирования:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("edit_select_"))
async def edit_menu(callback: CallbackQuery, state: FSMContext):
    bath_id = int(callback.data.split("_")[2])
    bath = get_bathhouse_by_id(bath_id)
    
    if not bath:
        await callback.answer("❌ Баня не найдена")
        return
    
    # Сохраняем ID бани в состоянии
    await state.update_data(editing_bath_id=bath_id)
    
    # Формируем информационное сообщение
    text = f"<b>✏️ Редактирование бани #{bath['id']}</b>\n\n"
    text += f"<b>🏠 Название:</b> {bath['name']}\n"
    text += f"<b>📍 Адрес:</b> {bath['address']}\n"
    text += f"<b>💰 Цена:</b> {bath['price']} руб/час\n"
    text += f"<b>👥 Гости:</b> до {bath['guests']} человек\n"
    text += f"<b>📞 Контакт:</b> {bath['contact']}\n"
    
    if bath['description']:
        text += f"<b>📝 Описание:</b> {bath['description'][:100]}...\n"
    
    photo_count = len(bath.get('photos', []))
    text += f"<b>📸 Фото:</b> {photo_count} шт.\n\n"
    text += "<b>Выберите что редактировать:</b>"
    
    # Создаем клавиатуру с полями для редактирования
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Название", callback_data=f"edit_field_name_{bath_id}")
    builder.button(text="📍 Адрес", callback_data=f"edit_field_address_{bath_id}")
    builder.button(text="💰 Цена", callback_data=f"edit_field_price_{bath_id}")
    builder.button(text="👥 Гости", callback_data=f"edit_field_guests_{bath_id}")
    builder.button(text="📞 Контакт", callback_data=f"edit_field_contact_{bath_id}")
    builder.button(text="📝 Описание", callback_data=f"edit_field_description_{bath_id}")
    builder.button(text="🗑️ УДАЛИТЬ БАНЮ", callback_data=f"edit_delete_confirm_{bath_id}")
    builder.button(text="🔙 Назад", callback_data="back_to_edit_list")
    builder.adjust(2)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_field_"))
async def edit_field_start(callback: CallbackQuery, state: FSMContext):
    # Формат: edit_field_НАЗВАНИЕПОЛЯ_ID
    parts = callback.data.split("_")
    field = parts[2]  # name, address, price, guests, contact, description
    bath_id = int(parts[3])
    
    field_names = {
        "name": "название",
        "address": "адрес",
        "price": "цену",
        "guests": "количество гостей",
        "contact": "контакт",
        "description": "описание"
    }
    
    field_prompts = {
        "name": "Введите новое название бани:",
        "address": "Введите новый адрес:",
        "price": "Введите новую цену (в рублях за час):",
        "guests": "Введите новое максимальное количество гостей:",
        "contact": "Введите новый контакт (@username или телефон):",
        "description": "Введите новое описание:"
    }
    
    # Сохраняем информацию о редактировании
    await state.update_data(
        editing_bath_id=bath_id,
        editing_field=field
    )
    
    # Устанавливаем состояние для ожидания ввода
    await state.set_state(EditBathStates.editing)
    
    await callback.message.answer(
        f"✏️ <b>Редактирование {field_names.get(field, field)}</b>\n\n"
        f"{field_prompts.get(field, 'Введите новое значение:')}\n\n"
        f"<i>Для отмены нажмите кнопку ниже</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@dp.message(EditBathStates.editing)
async def edit_field_save(message: Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.set_state(AdminStates.admin_menu)
        await message.answer(
            "❌ Редактирование отменено",
            reply_markup=get_admin_keyboard()
        )
        return
    
    data = await state.get_data()
    bath_id = data.get('editing_bath_id')
    field = data.get('editing_field')
    
    if not bath_id or not field:
        await message.answer("❌ Ошибка данных. Начните заново.")
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Админ-панель", reply_markup=get_admin_keyboard())
        return
    
    # Получаем текущие данные бани
    bath = get_bathhouse_by_id(bath_id)
    if not bath:
        await message.answer("❌ Баня не найдена")
        await state.set_state(AdminStates.admin_menu)
        await message.answer("Админ-панель", reply_markup=get_admin_keyboard())
        return
    
    # Валидация в зависимости от поля
    if field in ['price', 'guests']:
        if not message.text.isdigit():
            await message.answer("❌ Введите число!")
            return
        bath[field] = int(message.text)
    else:
        bath[field] = message.text
    
    # Сохраняем изменения
    if update_bathhouse_in_db(bath_id, bath):
        await message.answer(
            f"✅ <b>Поле '{field}' успешно обновлено!</b>",
            parse_mode="HTML"
        )
        
        # Возвращаемся в меню редактирования
        await state.set_state(AdminStates.admin_menu)
        
        # Создаем новый callback для возврата в меню
        new_callback = type('obj', (object,), {
            'data': f"edit_select_{bath_id}",
            'message': message,
            'answer': lambda x: None
        })
        await edit_menu(new_callback, state)
    else:
        await message.answer("❌ Ошибка при сохранении")

@dp.callback_query(F.data.startswith("edit_delete_confirm_"))
async def delete_confirm(callback: CallbackQuery, state: FSMContext):
    bath_id = int(callback.data.split("_")[3])
    bath = get_bathhouse_by_id(bath_id)
    
    if not bath:
        await callback.answer("❌ Баня не найдена")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ДА, УДАЛИТЬ", callback_data=f"edit_delete_yes_{bath_id}")
    builder.button(text="❌ НЕТ, ОТМЕНА", callback_data=f"edit_select_{bath_id}")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</b>\n\n"
        f"Вы действительно хотите удалить баню:\n"
        f"<b>{bath['name']}</b>\n"
        f"📍 {bath['address']}\n\n"
        f"<i>Это действие нельзя отменить!</i>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_delete_yes_"))
async def delete_yes(callback: CallbackQuery, state: FSMContext):
    bath_id = int(callback.data.split("_")[3])
    bath = get_bathhouse_by_id(bath_id)
    
    if not bath:
        await callback.answer("❌ Баня не найдена")
        return
    
    if delete_bathhouse_from_db(bath_id):
        await callback.message.edit_text(
            f"✅ <b>БАНЯ УДАЛЕНА</b>\n\n"
            f"{bath['name']}\n"
            f"📍 {bath['address']}",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.admin_menu)
        await callback.message.answer(
            "Админ-панель",
            reply_markup=get_admin_keyboard()
        )
    else:
        await callback.answer("❌ Ошибка при удалении")

@dp.callback_query(F.data == "back_to_edit_list")
async def back_to_edit_list(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.admin_menu)
    await callback.message.delete()
    await edit_delete_start(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "back_to_admin_main")
async def back_to_admin_main(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.admin_menu)
    await callback.message.delete()
    await callback.message.answer(
        "👑 Админ-панель",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
# ========== НАЗАД ==========
@dp.callback_query(F.data == "back_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.admin_menu)
    await callback.message.delete()
    await callback.message.answer(
        "Админ-панель",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "back_photos")
async def back_to_photos(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.admin_menu)
    await manage_photos_start(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "back_to_edit")
async def back_to_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bath_id = data['edit_bath_id']
    bath = get_bathhouse_by_id(bath_id)
    
    if bath:
        await edit_menu(callback, state)
    await callback.answer()

# ========== ВЫХОД ИЗ АДМИНКИ ==========
@dp.message(AdminStates.admin_menu, F.text == "🔙 Выход из админки")
async def exit_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню",
        reply_markup=get_main_keyboard()
    )

# ========== КЛИЕНТСКАЯ ЧАСТЬ ==========
@dp.message(F.text == "🔍 Найти баню")
async def find_bath(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Выберите способ поиска:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏠 Все бани")],
                [KeyboardButton(text="💰 По бюджету")],
                [KeyboardButton(text="👥 По гостям")],
                [KeyboardButton(text="📍 Поиск по адресу")],
                [KeyboardButton(text="🏠 На главную")]
            ],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🏠 Все бани")
async def show_all(message: Message, state: FSMContext):
    await state.clear()
    baths = get_bathhouses_from_db()
    
    if not baths:
        await message.answer("Нет бань", reply_markup=get_main_keyboard())
        return
    
    await message.answer(f"Найдено бань: {len(baths)}", reply_markup=get_main_keyboard())
    
    for bath in baths:
        await send_bathhouse_card(message, bath)
        await asyncio.sleep(1)

@dp.message(F.text == "💰 По бюджету")
async def by_budget_start(message: Message, state: FSMContext):
    await state.set_state(SearchStates.budget)
    await message.answer(
        "Введите максимальную цену:",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(SearchStates.budget, F.text.regexp(r'^\d+$'))
async def by_budget_process(message: Message, state: FSMContext):
    budget = int(message.text)
    baths = get_bathhouses_from_db()
    filtered = [b for b in baths if b['price'] <= budget]
    
    if not filtered:
        await message.answer(f"Нет бань до {budget} руб", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    await message.answer(f"Найдено: {len(filtered)}", reply_markup=get_main_keyboard())
    
    for bath in filtered[:5]:
        await send_bathhouse_card(message, bath)
        await asyncio.sleep(1)
    
    await state.clear()

@dp.message(F.text == "👥 По гостям")
async def by_guests_start(message: Message, state: FSMContext):
    await state.set_state(SearchStates.guests)
    await message.answer(
        "Введите количество человек:",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(SearchStates.guests, F.text.regexp(r'^\d+$'))
async def by_guests_process(message: Message, state: FSMContext):
    guests = int(message.text)
    baths = get_bathhouses_from_db()
    filtered = [b for b in baths if b['guests'] >= guests]
    
    if not filtered:
        await message.answer(f"Нет бань для {guests} чел", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    await message.answer(f"Найдено: {len(filtered)}", reply_markup=get_main_keyboard())
    
    for bath in filtered[:5]:
        await send_bathhouse_card(message, bath)
        await asyncio.sleep(1)
    
    await state.clear()

@dp.message(F.text == "📍 Поиск по адресу")
async def search_by_address_start(message: Message, state: FSMContext):
    """Начало поиска по адресу"""
    await state.set_state(SearchStates.address)
    await message.answer(
        "📍 <b>Поиск бань рядом с адресом</b>\n\n"
        "Введите адрес (например: Москва, ул. Тверская, 1):\n\n"
        "<i>Бот покажет бани в радиусе 10 км от указанного адреса</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@dp.message(SearchStates.address)
async def search_by_address_process(message: Message, state: FSMContext):
    """Обработка поиска по адресу"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Поиск отменен", reply_markup=get_main_keyboard())
        return
    
    address = message.text
    await message.answer("🔍 Ищу бани рядом с указанным адресом...")
    
    # Получаем координаты введенного адреса
    coords = geocode_address(address)
    
    if not coords:
        await message.answer(
            "❌ Не удалось найти указанный адрес. Попробуйте ввести более точный адрес.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    lat, lon = coords
    print(f"📍 Координаты адреса: {lat}, {lon}")
    
    # Получаем все бани
    baths = get_bathhouses_from_db()
    nearby_baths = []
    
    # Для каждой бани пытаемся получить координаты по её адресу
    for bath in baths:
        bath_coords = geocode_address(bath['address'])
        if bath_coords:
            dist = calculate_distance(coords, bath_coords)
            if dist <= 10:  # В радиусе 10 км
                nearby_baths.append({
                    'bath': bath,
                    'distance': round(dist, 1)
                })
                print(f"✅ {bath['name']} - {dist:.1f} км")
    
    # Сортируем по расстоянию
    nearby_baths.sort(key=lambda x: x['distance'])
    
    if not nearby_baths:
        await message.answer(
            f"🏠 <b>В радиусе 10 км от адреса:</b>\n{address}\n\n"
            f"❌ Бани не найдены",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Отправляем результаты
    await message.answer(
        f"📍 <b>Бани рядом с адресом:</b>\n{address}\n\n"
        f"🏠 <b>Найдено:</b> {len(nearby_baths)}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    for item in nearby_baths[:10]:  # Показываем не больше 10
        bath = item['bath']
        dist_text = f"🚗 <b>{item['distance']} км</b>"
        
        # Отправляем карточку с информацией о расстоянии
        text = f"<b>🏠 {bath['name']}</b>\n"
        text += f"{dist_text}\n\n"
        text += f"📍 <b>Адрес:</b> {bath['address']}\n"
        text += f"👥 <b>Гости:</b> до {bath['guests']} человек\n"
        text += f"💰 <b>Цена:</b> {bath['price']} руб/час\n"
        
        if bath['description']:
            text += f"📝 <b>Описание:</b> {bath['description'][:100]}\n"
        
        if bath['contact'].startswith('@'):
            text += f"\n💬 <b>Telegram:</b> {bath['contact']}"
        elif bath['contact'].startswith('+'):
            text += f"\n📞 <b>Телефон:</b> {bath['contact']}"
        
        keyboard = None
        contact_button = get_contact_button(bath['contact'])
        if contact_button:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[contact_button]])
        
        # Отправляем фото если есть
        photos = bath.get('photos', [])
        if photos and os.path.exists(photos[0]):
            try:
                photo = FSInputFile(photos[0])
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
        else:
            await bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        await asyncio.sleep(0.5)
    
    await state.clear()

@dp.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message, state: FSMContext):
    await state.clear()
    help_text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "🏠 <b>Все бани</b> - показать все доступные бани\n"
        "💰 <b>По бюджету</b> - поиск по максимальной цене\n"
        "👥 <b>По гостям</b> - поиск по количеству человек\n"
        "📍 <b>Поиск по адресу</b> - найти бани рядом с адресом\n"
        "📞 <b>Контакты</b> - информация о боте\n\n"
        "<b>Как забронировать:</b>\n"
        "1. Найдите подходящую баню\n"
        "2. В карточке бани указаны контакты владельца\n"
        "3. Если указан Telegram (@username), он будет кликабельным\n"
        "4. Свяжитесь с владельцем для бронирования"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(F.text == "📞 Контакты")
async def contacts_message(message: Message, state: FSMContext):
    await state.clear()
    contacts_text = (
        "📞 <b>Контакты</b>\n\n"
        "<b>По вопросам работы бота:</b>\n"
        "👤 Администратор: @findmitrie\n\n"
        "<b>Для бронирования бани:</b>\n"
        "• Найдите баню через поиск\n"
        "• В карточке указаны контакты владельца\n"
        "• Telegram-контакты (@username) кликабельны"
    )
    await message.answer(contacts_text, parse_mode="HTML", reply_markup=get_main_keyboard())

@dp.message(F.text == "🏠 На главную")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Главное меню",
        reply_markup=get_main_keyboard()
    )

# ========== ТЕСТОВЫЕ КОМАНДЫ ДЛЯ АДМИНА ==========
@dp.message(Command("test_photo"))
async def test_photo_command(message: Message):
    """Тестовая команда для проверки отправки фото"""
    if message.from_user.id != ADMIN_ID:
        return
    
    # Берем первое фото из папки
    photos = os.listdir(PHOTOS_DIR)
    if not photos:
        await message.answer("Нет фото в папке")
        return
    
    test_photo = os.path.join(PHOTOS_DIR, photos[0])
    await message.answer(f"Тестируем фото: {photos[0]}")
    
    try:
        photo = FSInputFile(test_photo)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="Тестовое фото"
        )
        await message.answer("✅ Фото отправлено успешно!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        
        # Пробуем сконвертировать
        converted = convert_image_to_jpg(test_photo)
        if converted:
            try:
                photo = FSInputFile(converted)
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption="Сконвертированное тестовое фото"
                )
                await message.answer("✅ Сконвертированное фото отправлено!")
            except Exception as e2:
                await message.answer(f"❌ Ошибка и с конвертированным: {e2}")

@dp.message(Command("fix_photos"))
async def fix_photos_command(message: Message):
    """Очистка дубликатов фото в БД"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("🔍 Проверяю дубликаты фото...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Находим дубликаты
    cursor.execute("""
        SELECT photo_path, COUNT(*) as cnt 
        FROM bathhouse_photos 
        GROUP BY photo_path 
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    
    deleted = 0
    for dup in duplicates:
        photo_path = dup['photo_path']
        # Удаляем все кроме одного
        cursor.execute("""
            DELETE FROM bathhouse_photos 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM bathhouse_photos 
                WHERE photo_path = ?
            ) AND photo_path = ?
        """, (photo_path, photo_path))
        deleted += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Удалено дубликатов: {deleted}")
    await check_and_fix_photos()  # Запускаем обычную проверку

@dp.message(Command("cleanup"))
async def cleanup_command(message: Message):
    """Очистка базы данных от битых ссылок"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("🧹 Начинаю очистку...")
    await check_and_fix_photos()
    await message.answer("✅ Очистка завершена!")

# ========== ЗАПУСК ==========
async def main():
    print("=" * 50)
    print("🚀 ЗАПУСК БОТА")
    print("=" * 50)
    
    # Проверяем фото перед запуском
    await check_and_fix_photos()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")