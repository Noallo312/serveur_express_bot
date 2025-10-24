from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
import os

ADMIN_ID = 6976573567
user_data = {}

# Message d'accueil avec emoji
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🛒 Commander", callback_data='order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bonjour ! Cliquez sur 🛒 Commander pour passer votre commande.",
        reply_markup=reply_markup
    )

# Bouton Commander
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'order':
        await context.bot.send_message(chat_id=query.from_user.id, text="📸 Envoyez une photo de votre panier.")
        user_data[query.from_user.id] = {"step": "photo"}

# Formulaire étape par étape
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_data:
        step = user_data[user_id]["step"]

        # Étape photo
        if step == "photo" and update.message.photo:
            user_data[user_id]["photo"] = update.message.photo[-1].file_id
            user_data[user_id]["step"] = "prix"
            await update.message.reply_text("💰 Indiquez le prix (20€ à 23€) :")

        # Étape prix
        elif step == "prix":
            try:
                prix = float(update.message.text.replace(",", "."))
                if 20 <= prix <= 23:
                    user_data[user_id]["prix"] = prix
                    user_data[user_id]["step"] = "adresse"
                    await update.message.reply_text("🏠 Indiquez votre adresse :")
                else:
                    await update.message.reply_text("⚠️ Le prix doit être entre 20€ et 23€. Réessayez :")
            except ValueError:
                await update.message.reply_text("⚠️ Veuillez entrer un nombre valide :")

        # Étape adresse
        elif step == "adresse":
            user_data[user_id]["adresse"] = update.message.text
            keyboard = [
                [InlineKeyboardButton("💳 PayPal", callback_data='paypal')],
                [InlineKeyboardButton("🏦 Virement", callback_data='virement')],
                [InlineKeyboardButton("📲 Revolut", callback_data='revolut')]
            ]
            await update.message.reply_text("Choisissez un mode de paiement :", reply_markup=InlineKeyboardMarkup(keyboard))
            user_data[user_id]["step"] = "paiement"

# Choix paiement et envoi de la commande
async def payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data[user_id]["paiement"] = query.data

    info = user_data[user_id]

    # Envoi de la commande à l'admin
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=info["photo"],
        caption=f"📦 Nouvelle commande :\n💰 Prix: {info['prix']}€\n🏠 Adresse: {info['adresse']}\n💳 Paiement: {info['paiement']}"
    )

    await query.message.reply_text("✅ Votre commande a été envoyée ! Merci 😊")
    user_data.pop(user_id)

# Token depuis les variables d'environnement
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Configuration du bot
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button, pattern='^order$'))
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.add_handler(CallbackQueryHandler(payment_choice, pattern='^(paypal|virement|revolut)$'))

app.run_polling()
