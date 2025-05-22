import pandas as pd
import os
TOKEN = os.getenv("BOT_TOKEN")
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ContextTypes
)
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
drinks_data = None

def load_drinks():
    global drinks_data
    if drinks_data is None:
        try:
            drinks_data = pd.read_excel(
                "data/Напитки КСВ 1.0 (1).xlsx", 
                sheet_name=None,
                engine='openpyxl'
            )
            
            # Создаем общий DataFrame для поиска
            all_drinks = []
            for sheet_name, df in drinks_data.items():
                df['Категория'] = sheet_name
                all_drinks.append(df)
            
            drinks_data['Все'] = pd.concat(all_drinks, ignore_index=True)
            logger.info("Данные успешно загружены")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            raise
    
    return drinks_data

def format_abv(value):
    try:
        if isinstance(value, str) and '%' in value:
            return value
        
        num = float(value)
        
        if num < 1:
            result = num * 100
            return f"{result:.1f}%".rstrip('0').rstrip('.') + "%"
        
        return f"{num:.1f}%".rstrip('0').rstrip('.') + "%"
    except:
        return "—"

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Поиск", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("🥃 Виски", callback_data="category_Виски"),
         InlineKeyboardButton("🏴‍☠️ Ром", callback_data="category_Ром")],
        [InlineKeyboardButton("🍶 Текила", callback_data="category_Текила"),
         InlineKeyboardButton("🥂 Коньяк", callback_data="category_Коньяк и бренди")],
        [InlineKeyboardButton("🌀 Джин", callback_data="category_Джин"),
         InlineKeyboardButton("🥛 Водка", callback_data="category_Водка")],
        [InlineKeyboardButton("🍹 Коктейли", callback_data="category_Классика")]
    ])

def back_buttons(category):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data=f"category_{category}")],
        [InlineKeyboardButton("🏠 В меню", callback_data="main_menu")]
    ])

def format_drink(drink, is_cocktail=False):
    response = f"<b>{drink['Наименование']}</b>\n"
    response += f"<i>Категория: {drink['Категория']}</i>\n\n"
    
    fields = {
        "🌍 Страна": drink.get('Страна'),
        "⚡ Крепость": format_abv(drink.get('Крепость')),
        "👅 Вкус": drink.get('Вкус'),
        "👃 Аромат": drink.get('Аромат'),
        "🌾 Сырье": drink.get('Сырье/Сорт винограда'),
        "📝 Описание": drink.get('Описание')
    } if not is_cocktail else {
        "⚡ Крепость": format_abv(drink.get('Крепость')),
        "👅 Вкус": drink.get('Вкус'),
        "👃 Аромат": drink.get('Аромат'),
        "📦 Состав": drink.get('Состав'),
        "🔧 Метод": drink.get('Метод приготовления'),
        "📝 Описание": drink.get('Описание')
    }
    
    for key, value in fields.items():
        if pd.notna(value) and value not in [None, "", "-"]:
            response += f"{key}: {value}\n"
    
    return response

async def search_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.inline_query.query.strip()
        logger.info(f"Поисковый запрос: '{query}'")
        
        if not query:
            return
        
        all_drinks = load_drinks()['Все']
        
        # Улучшенный поиск с обработкой NaN и пустых значений
        found = all_drinks[
            all_drinks['Наименование'].notna() &
            all_drinks['Наименование'].str.lower().str.contains(
                query.lower(), 
                na=False, 
                regex=False
            )
        ].head(20)
        
        logger.info(f"Найдено результатов: {len(found)}")
        
        results = []
        for idx, drink in found.iterrows():
            is_cocktail = (drink['Категория'] == 'Классика')
            description = format_drink(drink, is_cocktail)
            
            results.append(
                InlineQueryResultArticle(
                    id=str(idx),
                    title=drink['Наименование'],
                    description=f"{drink['Категория']} • {format_abv(drink.get('Крепость'))}",
                    input_message_content=InputTextMessageContent(
                        message_text=description,
                        parse_mode="HTML"
                    )
                )
            )
        
        await update.inline_query.answer(results)
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении поиска: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "main_menu":
            await query.edit_message_text(
                "🍸 Выберите категорию напитков:",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
            return
        
        if query.data.startswith("category_"):
            category = query.data.replace("category_", "")
            data = load_drinks().get(category)
            
            if data is None or data.empty:
                await query.edit_message_text("❌ Категория не найдена")
                return
            
            buttons = [
                InlineKeyboardButton(
                    row['Наименование'], 
                    callback_data=f"drink_{category}_{idx}"
                )
                for idx, row in data.iterrows()
            ]
            
            keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
            keyboard.append([InlineKeyboardButton("🏠 В меню", callback_data="main_menu")])
            
            await query.edit_message_text(
                f"📋 Выберите напиток из категории {category}:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        
        elif query.data.startswith("drink_"):
            _, category, index = query.data.split("_")
            data = load_drinks().get(category)
            
            try:
                drink = data.loc[int(index)]
                is_cocktail = (category == "Классика")
                response = format_drink(drink, is_cocktail)
                await query.edit_message_text(
                    response,
                    reply_markup=back_buttons(category),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка загрузки напитка: {e}")
                await query.edit_message_text("❌ Ошибка загрузки данных")
                
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🍸 Добро пожаловать в цифровую барную карту!\n\n"
        "Используйте:\n"
        "• Кнопки меню для навигации\n"
        "• @имя_бота [название] для поиска\n"
        "• /start для обновления меню",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

if __name__ == "__main__":
    try:
        app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(InlineQueryHandler(search_results))
        
        logger.info("Бот успешно запущен")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
