import tkinter as tk
from tkinter import font, messagebox
import sqlite3
import os
import datetime
import sys
import winsound  # Только для Windows. Для Mac/Linux нужно убрать или заменить.
from PIL import Image, ImageTk  # Установите: pip install Pillow

"""
TrackBox
© 2026 Геннадий <Фамилия>
Лицензия: GNU Affero General Public License v3.0
Полный текст лицензии см. в файле LICENSE
или на сайте:
https://www.gnu.org/licenses/agpl-3.0.html
"""

# =====================================================
# НАСТРОЙКИ
# =====================================================

# 📁 Пути к базам данных (можно менять)
DB_FOLDER = r"TrackPeople"
CARDS_DB = "logs.db"  # Журнал операций
EMPLOYEES_DB = "employees.db"  # Справочник сотрудников

# 📸 Путь к папке с фотографиями (можно указать сетевой путь!)
PHOTO_FOLDER = r"photo"

# 🔒 Код разблокировки (сканирование этого кода завершает операцию)
UNLOCK_CODE = "0"

# =====================================================
# DARK THEME
# =====================================================

BG_MAIN = "#202020"
BG_PANEL = "#2B2B2B"

BLUE = "#4CC2FF"
BLUE_LIGHT = "#333F4D"

TEXT = "#F3F3F3"
TEXT_LIGHT = "#B8B8B8"

SUCCESS = "#17E417"
WARNING = "#FFD54F"
ERROR = "#FF6B6B"

BORDER = "#444444"

STATUS_BG = "#0F6CBD"
STATUS_FG = "#FFFFFF"

EMP_NAME_FG = "#FFFFFF"
EMP_POSITION_FG = "#B8B8B8"

CELLS_LIST_BG = "#333F4D"
CELLS_LIST_FG = "#FFFFFF"

LOCK_BG = "#4A4020"

HISTORY_BG = "#2B2B2B"
HISTORY_FG = "#F3F3F3"

# =====================================================
# ПОДДЕРЖКА PYINSTALLER (.exe)
# =====================================================
def get_resource_path(relative_path):
    """Получить абсолютный путь к ресурсу, работает для dev и PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Определяем базовую директорию (для .exe)
if getattr(sys, 'frozen', False):
    # Запущено как .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Запущено как скрипт
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Полные пути к БД
DB_FOLDER_ABS = os.path.join(BASE_DIR, DB_FOLDER)
PHOTO_FOLDER_ABS = PHOTO_FOLDER if os.path.isabs(PHOTO_FOLDER) else os.path.join(BASE_DIR, PHOTO_FOLDER)

os.makedirs(DB_FOLDER_ABS, exist_ok=True)
os.makedirs(PHOTO_FOLDER_ABS, exist_ok=True)

path_logs = os.path.join(DB_FOLDER_ABS, CARDS_DB)
path_emp = os.path.join(DB_FOLDER_ABS, EMPLOYEES_DB)

# =====================================================
# ИНИЦИАЛИЗАЦИЯ БАЗ ДАННЫХ
# =====================================================

# 1. База сотрудников (Справочник)
emp_conn = sqlite3.connect(path_emp)
emp_cur = emp_conn.cursor()

# Создаём таблицу с новым столбцом position
emp_cur.execute("""
CREATE TABLE IF NOT EXISTS employees (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    position TEXT
)
""")

# 🔧 Миграция: добавляем столбец position, если его нет (для старых баз)
try:
    emp_cur.execute("ALTER TABLE employees ADD COLUMN position TEXT")
    emp_conn.commit()
    print("✅ Добавлен столбец 'position' в таблицу сотрудников")
except sqlite3.OperationalError:
    # Столбец уже существует
    pass

# Добавим тестовых сотрудников (если таблица пустая)
emp_cur.execute("SELECT count(*) FROM employees")
if emp_cur.fetchone()[0] == 0:
    test_data = [
        ("1234567890", "Джон Уик", "Кладовщик"),
        ("0987654321", "Джек Воробей", "Водитель"),
        ("1111111111", "Филлип Джей Фрай", "Менеджер")
    ]
    emp_cur.executemany("INSERT INTO employees (code, name, position) VALUES (?, ?, ?)", test_data)
    emp_conn.commit()
    print("✅ Создан справочник с тестовыми сотрудниками")

# 2. База логов (Журнал выдач)
log_conn = sqlite3.connect(path_logs)
log_cur = log_conn.cursor()

# 🔧 ИСПРАВЛЕНИЕ: Создаём таблицу с emp_position сразу
log_cur.execute("""
CREATE TABLE IF NOT EXISTS issue_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emp_code TEXT,
    emp_name TEXT,
    emp_position TEXT,
    cells TEXT,
    dt TEXT
)
""")

# 🔧 Миграция: добавляем emp_position, если его нет (для старых баз!)
try:
    log_cur.execute("ALTER TABLE issue_log ADD COLUMN emp_position TEXT")
    log_conn.commit()
    print("✅ Добавлен столбец 'emp_position' в таблицу логов")
except sqlite3.OperationalError:
    # Столбец уже существует
    pass

log_conn.commit()

# =====================================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ
# =====================================================
current_emp_code = None
current_emp_name = None
current_emp_position = None
scanned_cells = []
current_photo = None
is_locked = False  # 🔒 Блокировка приёма новых карт

# =====================================================
# ИНТЕРФЕЙС
# =====================================================
root = tk.Tk()
root.title("TrackBox by Gen Pol")
root.geometry("700x550")
root.configure(bg=BG_MAIN)  # теперь используется переменная

# Шрифты
font_title = font.Font(family="Segoe UI", size=16, weight="bold")
font_status = font.Font(family="Segoe UI", size=13)
font_big = font.Font(family="Segoe UI", size=22, weight="bold")
font_position = font.Font(family="Segoe UI", size=16, slant="italic")
font_cells = font.Font(family="Consolas", size=22, weight="bold")
font_mono = font.Font(family="Consolas", size=10)

# --- Верхняя панель: Статус ---
lbl_status = tk.Label(root, text="👋 Приложите ПРОПУСК сотрудника", font=font_title,
                      bg=STATUS_BG, fg=STATUS_FG)
lbl_status.pack(pady=15)

# --- Центральная панель: Инфо о текущем процессе ---
frame_info = tk.Frame(root, bg=BG_PANEL, relief="ridge", bd=2)
frame_info.pack(fill="both", expand=True, padx=20, pady=10)

# Фото сотрудника
lbl_photo = tk.Label(frame_info, bg=BG_PANEL, relief="solid", bd=1)
lbl_photo.pack(pady=10)

# Имя сотрудника (зелёный)
lbl_emp_name = tk.Label(frame_info, text="", font=font_big, bg=BG_PANEL, fg=EMP_NAME_FG)
lbl_emp_name.pack(pady=5)

# Должность (синий, под именем)
lbl_emp_position = tk.Label(frame_info, text="", font=font_position, bg=BG_PANEL, fg=EMP_POSITION_FG)
lbl_emp_position.pack(pady=3)

# Подсказка по ячейкам
lbl_cells_hint = tk.Label(frame_info, text="Ожидание сканирования ячеек...", font=font_status,
                          bg=BG_PANEL, fg=TEXT_LIGHT)
lbl_cells_hint.pack(pady=5)

# Список отсканированных ячеек
lbl_cells_list = tk.Label(frame_info, text="", font=font_cells,
                          bg=CELLS_LIST_BG, fg=CELLS_LIST_FG, relief="sunken", bd=1)
lbl_cells_list.pack(fill="x", padx=20, pady=10, ipady=10)

# Индикатор блокировки
lbl_lock_status = tk.Label(frame_info, text="", font=("Segoe UI", 11),
                           bg=LOCK_BG, fg=WARNING)
lbl_lock_status.pack(fill="x", padx=20, pady=5)

# --- Нижняя панель: История (последние 3 операции) ---
lbl_hist_title = tk.Label(root, text="📋 Последние операции:", font=font_status,
                          bg=BG_MAIN, fg=TEXT_LIGHT)
lbl_hist_title.pack(pady=(10, 0))

history_labels = []
for i in range(3):
    lbl = tk.Label(root, text="", anchor="w", font=font_mono,
                   bg=HISTORY_BG, fg=HISTORY_FG)
    lbl.pack(fill="x", padx=20)
    history_labels.append(lbl)

# --- Скрытое поле ввода (ловит сканер) ---
entry = tk.Entry(root, font=font_big)
entry.pack(pady=10)
entry.focus_set()


# =====================================================
# ФУНКЦИИ
# =====================================================

def beep_success():
    try:
        winsound.Beep(800, 150)
    except:
        pass


def beep_error():
    try:
        winsound.Beep(300, 400)
    except:
        pass


def beep_warning():
    try:
        winsound.Beep(500, 200)
    except:
        pass


def mask_card_code(code):
    """Маскирует код карты, оставляя только последние 3 символа"""
    if len(code) <= 3:
        return code
    return "*" * (len(code) - 3) + code[-3:]


def get_employee_info(code):
    """Возвращает имя и должность сотрудника по коду"""
    try:
        emp_cur.execute("SELECT name, position FROM employees WHERE code = ?", (code,))
        row = emp_cur.fetchone()
        if row:
            return row[0], row[1] if row[1] else ""
        return None, None
    except:
        return None, None


def load_employee_photo(emp_name):
    """Загружает фото по имени сотрудника (без расширения)."""
    if not emp_name:
        return None

    extensions = [".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"]
    for ext in extensions:
        path = os.path.join(PHOTO_FOLDER_ABS, f"{emp_name}{ext}")
        if os.path.exists(path):
            try:
                img = Image.open(path)
                img.thumbnail((600, 300))
                photo = ImageTk.PhotoImage(img)
                return photo
            except Exception as e:
                print(f"Ошибка загрузки фото {path}: {e}")
                return None
    return None


def save_to_db(emp_code, emp_name, emp_position, cells_list):
    """Сохраняет операцию в журнал (даже если ячеек нет)"""
    cells_str = ", ".join(cells_list) if cells_list else "ничего не взял"
    now = datetime.datetime.now().strftime("%d.%m %H:%M")

    log_cur.execute("""
        INSERT INTO issue_log (emp_code, emp_name, emp_position, cells, dt)
        VALUES (?, ?, ?, ?, ?)
    """, (emp_code, emp_name if emp_name else "Неизвестный", emp_position if emp_position else "", cells_str, now))
    log_conn.commit()

    refresh_history()
    beep_success()


def refresh_history():
    """Обновляет панель истории"""
    log_cur.execute("SELECT emp_name, emp_position, cells, dt FROM issue_log ORDER BY id DESC LIMIT 3")
    rows = log_cur.fetchall()

    for lbl, row in zip(history_labels, rows):
        name, position, cells, dt = row
        pos_text = f" ({position})" if position else ""
        lbl.config(text=f"[{dt}] {name}{pos_text} ➜ {cells}")

    for i in range(len(rows), 3):
        history_labels[i].config(text="")


def reset_state():
    """Сбрасывает состояние и разблокирует приём карт"""
    global current_emp_code, current_emp_name, current_emp_position, scanned_cells, current_photo, is_locked

    current_emp_code = None
    current_emp_name = None
    current_emp_position = None
    scanned_cells = []
    current_photo = None
    is_locked = False

    lbl_status.config(text="👋 Приложите ПРОПУСК сотрудника", fg=STATUS_FG)
    lbl_emp_name.config(text="")
    lbl_emp_position.config(text="")
    lbl_cells_hint.config(text="Ожидание сканирования ячеек...", fg=TEXT_LIGHT)
    lbl_cells_list.config(text="")
    lbl_photo.config(image="")
    lbl_lock_status.config(text="")
    entry.focus_set()


def complete_operation():
    """Завершает текущую операцию: сохраняет и сбрасывает"""
    global is_locked

    if current_emp_code is not None:
        save_to_db(current_emp_code, current_emp_name, current_emp_position, scanned_cells)
        print(f"✅ Операция завершена: {current_emp_name or 'Неизвестный'}, ячеек: {len(scanned_cells)}")

    reset_state()


def process_scan(event=None):
    """Обрабатывает сканирование (карта, ячейка или код разблокировки)"""
    global current_emp_code, current_emp_name, current_emp_position, scanned_cells, current_photo, is_locked

    raw_value = entry.get().strip()
    entry.delete(0, tk.END)

    if not raw_value:
        return

    # 🔓 Код разблокировки "0" — завершает операцию
    if raw_value == UNLOCK_CODE:
        if current_emp_code is not None:
            complete_operation()
        else:
            lbl_status.config(text="⚠️ Нет активной операции для завершения", fg=WARNING)
            beep_warning()
        return

    # 🔒 Если заблокировано — игнорируем новые карты
    if is_locked and len(raw_value) > 5:
        lbl_status.config(text="🔒 Ожидается код завершения (0). Карта не принята.", fg=ERROR)
        beep_error()
        return

    # Определяем тип сканирования
    if len(raw_value) > 5:
        # ===== Это карта сотрудника =====

        # Если уже был сотрудник — сохраняем предыдущую операцию
        if current_emp_code is not None:
            save_to_db(current_emp_code, current_emp_name, current_emp_position, scanned_cells)

        current_emp_code = raw_value
        current_emp_name, current_emp_position = get_employee_info(raw_value)
        scanned_cells = []

        # Загружаем фото
        if current_emp_name:
            current_photo = load_employee_photo(current_emp_name)
            if current_photo:
                lbl_photo.config(image=current_photo)
            else:
                lbl_photo.config(image="")
        else:
            current_photo = None
            lbl_photo.config(image="")

        # Обновляем интерфейс
        if current_emp_name:
            # ✅ Известный сотрудник
            lbl_status.config(text=f"✅ Сотрудник: {current_emp_name}", fg=SUCCESS)
            lbl_emp_name.config(text=current_emp_name, fg=EMP_NAME_FG)
            lbl_emp_position.config(text=current_emp_position if current_emp_position else "Должность не указана",
                                    fg=EMP_POSITION_FG)
        else:
            # ⚠️ Неизвестный сотрудник — маскируем код
            masked_code = mask_card_code(raw_value)
            lbl_status.config(text=f"⚠️ Не в базе", fg=WARNING)
            lbl_emp_name.config(text=f"Не добавлен в базу", fg=EMP_NAME_FG)
            lbl_emp_position.config(text=f"код карты: {masked_code}", fg=EMP_POSITION_FG)

        # 🔒 Блокируем приём новых карт
        is_locked = True
        lbl_lock_status.config(text="🔒 Завершите операцию кодом 0 перед следующей картой")

        lbl_cells_hint.config(text="📦 Сканируйте штрих-коды ЯЧЕЕК (можно несколько)", fg=EMP_POSITION_FG)
        lbl_cells_list.config(text="")
        beep_success()
        return

    # ===== Это ячейка (длина <=5) =====
    if current_emp_code is None:
        lbl_status.config(text="❌ Сначала приложите ПРОПУСК сотрудника!", fg=ERROR)
        beep_error()
        return

    scanned_cells.append(raw_value)
    lbl_cells_list.config(text="\n".join(scanned_cells))
    lbl_cells_hint.config(text=f"Отсканировано ячеек: {len(scanned_cells)}", fg=SUCCESS)
    beep_success()
    entry.focus_set()


# =====================================================
# ЗАПУСК
# =====================================================
entry.bind("<Return>", process_scan)
entry.bind("<Tab>", process_scan)

# Подсказка при старте
print("=" * 60)
print("🚀 TrackBox запущен")
print("=" * 60)
print(f"📁 Базы данных: {os.path.abspath(DB_FOLDER_ABS)}")
print(f"📸 Фотографии: {os.path.abspath(PHOTO_FOLDER_ABS)}")
print(f"🔓 Код завершения операции: {UNLOCK_CODE}")
print("=" * 60)
print("📋 Тестовые карты: 1234567890, 0987654321, 1111111111")
print("📦 Ячейки: любой код ≤5 символов (например, 0001, A12)")
print("🔒 Для завершения операции отсканируйте код: 0")
print("=" * 60)

root.mainloop()

# Закрытие соединений при выходе
emp_conn.close()
log_conn.close()