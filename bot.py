import os
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from flask import Flask

# ---------------------------
# Flask pour garder le bot actif
# ---------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot actif et en ligne 🚀"

def run():
    app.run(host="0.0.0.0", port=3000)

threading.Thread(target=run).start()

# ---------------------------
# Bot Telegram
# ---------------------------

# Liste des admins qui reçoivent les commandes
ADMINS = [6976573567, 6193535472]

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🛒 Commander", callback_data='order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bonjour ! Bienvenue sur le service Serveur Express.\n"
        "Cliquez sur 🛒 *Commander* pour passer votre commande.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'order':
        await context.bot.send_message(chat_id=query.from_user.id, text="📸 Envoyez une photo de votre panier 🛍️.")
        user_data[query.from_user.id] = {"step": "photo"}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_data:
        step = user_data[user_id]["step"]

        # Étape photo
        if step == "photo" and update.message.photo:
            user_data[user_id]["photo"] = update.message.photo[-1].file_id
            user_data[user_id]["step"] = "prix"
            await update.message.reply_text("💰 Indiquez le prix (entre 20 € et 23 €) :")

        # Étape prix
        elif step == "prix":
            try:
                prix = float(update.message.text.replace(",", "."))
                if 20 <= prix <= 23:
                    user_data[user_id]["prix"] = prix
                    user_data[user_id]["step"] = "adresse"
                    await update.message.reply_text("🏠 Indiquez votre adresse complète :")
                else:
                    await update.message.reply_text("⚠️ Le prix doit être compris entre 20 € et 23 €. Réessayez 💸 :")
            except ValueError:
                await update.message.reply_text("⚠️ Veuillez entrer un nombre valide (exemple : 21.5).")

        # Étape adresse
        elif step == "adresse":
            user_data[user_id]["adresse"] = update.message.text
            keyboard = [
                [InlineKeyboardButton("💳 PayPal", callback_data='paypal')],
                [InlineKeyboardButton("🏦 Virement", callback_data='virement')],
                [InlineKeyboardButton("📲 Revolut", callback_data='revolut')]
            ]
            await update.message.reply_text(
                "💰 Choisissez un mode de paiement ci-dessous 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            user_data[user_id]["step"] = "paiement"

async def payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data[user_id]["paiement"] = query.data

    info = user_data[user_id]

    # Envoi de la commande à tous les admins
    for admin_id in ADMINS:
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=info["photo"],
            caption=(
                "📦 *Nouvelle commande reçue* 🔔\n\n"
                f"💰 Prix : {info['prix']} €\n"
                f"🏠 Adresse : {info['adresse']}\n"
                f"💳 Paiement : {info['paiement']}"
            ),
            parse_mode="Markdown"
        )

    # Message de confirmation au client
    await query.message.reply_text(
        "✅ *Votre commande a bien été envoyée !* 🎉\n\n"
        "Merci pour votre confiance 🤝\n"
        "📦 Vous recevrez le lien de suivi d’ici peu 🚚💨",
        parse_mode="Markdown"
    )

    # Supprimer les données utilisateur
    user_data.pop(user_id)

# ---------------------------
# Lancement du bot
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(CallbackQueryHandler(button, pattern='^order$'))
app_bot.add_handler(MessageHandler(filters.ALL, handle_message))
app_bot.add_handler(CallbackQueryHandler(payment_choice, pattern='^(paypal|virement|revolut)$'))

app_bot.run_polling()
