import os
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# ---------------------------
# Base de données SQLite
# ---------------------------
def init_db():
    conn = sqlite3.connect('commandes.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS commandes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  prenom TEXT,
                  nom TEXT,
                  username TEXT,
                  prix REAL,
                  adresse TEXT,
                  paiement TEXT,
                  date TEXT,
                  photo_id TEXT)''')
    conn.commit()
    conn.close()

def save_commande(user_id, prenom, nom, username, prix, adresse, paiement, photo_id):
    conn = sqlite3.connect('commandes.db', check_same_thread=False)
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO commandes (user_id, prenom, nom, username, prix, adresse, paiement, date, photo_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, prenom, nom, username, prix, adresse, paiement, date, photo_id))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('commandes.db', check_same_thread=False)
    c = conn.cursor()
    
    # Total
    c.execute("SELECT COUNT(*) FROM commandes")
    total = c.fetchone()[0]
    
    # Aujourd'hui
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM commandes WHERE date LIKE ?", (f"{today}%",))
    today_count = c.fetchone()[0]
    
    # Ce mois
    month = datetime.now().strftime("%Y-%m")
    c.execute("SELECT COUNT(*) FROM commandes WHERE date LIKE ?", (f"{month}%",))
    month_count = c.fetchone()[0]
    
    # Revenu total
    c.execute("SELECT SUM(prix) FROM commandes")
    revenue = c.fetchone()[0] or 0
    
    conn.close()
    return total, today_count, month_count, revenue

def get_historique(limit=10):
    conn = sqlite3.connect('commandes.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''SELECT prenom, nom, username, prix, adresse, paiement, date 
                 FROM commandes ORDER BY id DESC LIMIT ?''', (limit,))
    results = c.fetchall()
    conn.close()
    return results

# ---------------------------
# Flask (pour le port requis par Render)
# ---------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot actif et hébergé sur Render 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# ---------------------------
# Bot Telegram
# ---------------------------

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

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        await update.message.reply_text("⛔ Cette commande est réservée aux administrateurs.")
        return
    
    total, today, month, revenue = get_stats()
    
    # Calcul des bénéfices (5€ par commande)
    benef_total = total * 5
    benef_today = today * 5
    benef_month = month * 5
    
    message = (
        "📊 *STATISTIQUES DU SERVICE*\n\n"
        f"📦 *Total commandes :* {total}\n"
        f"📅 *Aujourd'hui :* {today}\n"
        f"📆 *Ce mois :* {month}\n\n"
        f"💰 *Chiffre d'affaires total :* {revenue:.2f} €\n"
        f"💵 *Bénéfices totaux :* {benef_total:.2f} € ({total} × 5€)\n"
        f"📈 *Bénéfices du mois :* {benef_month:.2f} € ({month} × 5€)\n"
        f"🎯 *Bénéfices aujourd'hui :* {benef_today:.2f} € ({today} × 5€)\n"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def historique(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMINS:
        await update.message.reply_text("⛔ Cette commande est réservée aux administrateurs.")
        return
    
    commandes = get_historique(10)
    
    if not commandes:
        await update.message.reply_text("📭 Aucune commande enregistrée pour le moment.")
        return
    
    message = "📜 *HISTORIQUE DES 10 DERNIÈRES COMMANDES*\n\n"
    
    for i, cmd in enumerate(commandes, 1):
        prenom, nom, username, prix, adresse, paiement, date = cmd
        nom_complet = f"{prenom} {nom}".strip()
        message += (
            f"*{i}. {nom_complet}* ({username})\n"
            f"   💰 {prix}€ | 💳 {paiement}\n"
            f"   📍 {adresse[:30]}{'...' if len(adresse) > 30 else ''}\n"
            f"   🕐 {date}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'order':
        await context.bot.send_message(chat_id=query.from_user.id, text="📸 Envoyez une photo de votre panier 🛍️.")
        
        # Sauvegarder les infos du client
        user = query.from_user
        user_data[query.from_user.id] = {
            "step": "photo",
            "prenom": user.first_name,
            "nom": user.last_name or "",
            "username": f"@{user.username}" if user.username else "Pas de username",
            "user_id": user.id
        }

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in user_data:
        step = user_data[user_id]["step"]

        if step == "photo" and update.message.photo:
            user_data[user_id]["photo"] = update.message.photo[-1].file_id
            user_data[user_id]["step"] = "prix"
            await update.message.reply_text("💰 Indiquez le prix (entre 20 € et 23 €) :")

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
    
    # Préparer le nom complet
    nom_complet = f"{info['prenom']} {info['nom']}".strip()
    
    # Sauvegarder dans la base de données
    save_commande(
        user_id=info['user_id'],
        prenom=info['prenom'],
        nom=info['nom'],
        username=info['username'],
        prix=info['prix'],
        adresse=info['adresse'],
        paiement=info['paiement'],
        photo_id=info['photo']
    )

    # Envoi de la commande à tous les admins
    for admin_id in ADMINS:
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=info["photo"],
            caption=(
                "📦 *Nouvelle commande reçue* 🔔\n\n"
                f"👤 *Client :* {nom_complet}\n"
                f"📱 *Username :* {info['username']}\n"
                f"🆔 *ID Telegram :* `{info['user_id']}`\n\n"
                f"💰 *Prix :* {info['prix']} €\n"
                f"🏠 *Adresse :* {info['adresse']}\n"
                f"💳 *Paiement :* {info['paiement']}"
            ),
            parse_mode="Markdown"
        )

    # Confirmation utilisateur
    await query.message.reply_text(
        "✅ *Votre commande a bien été envoyée !* 🎉\n\n"
        "Merci pour votre confiance 🤝\n"
        "📦 Vous recevrez le lien de suivi d'ici peu 🚚💨",
        parse_mode="Markdown"
    )

    user_data.pop(user_id, None)

# ---------------------------
# Lancement du bot et du serveur
# ---------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")

def main():
    # Initialiser la base de données
    init_db()
    
    # Créer l'application bot
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Ajouter les handlers
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stats", stats))
    app_bot.add_handler(CommandHandler("historique", historique))
    app_bot.add_handler(CallbackQueryHandler(button, pattern='^order$'))
    app_bot.add_handler(MessageHandler(filters.ALL, handle_message))
    app_bot.add_handler(CallbackQueryHandler(payment_choice, pattern='^(paypal|virement|revolut)$'))

    # Lancer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Démarrer le bot Telegram (bloquant)
    print("🤖 Bot Telegram démarré...")
    print("📊 Base de données initialisée...")
    app_bot.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
