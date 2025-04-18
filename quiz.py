
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import discord
from discord.ext import commands


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

admin_ids = [586928057156108298]  # Buraya kendi Discord kullanıcı ID'ni ekle
scores_file = "user_scores.json"
questions_file = "sorular.json"

user_scores = {}
user_progress = {}

def load_scores():
    global user_scores
    if os.path.exists(scores_file):
        with open(scores_file, "r", encoding="utf-8") as f:
            user_scores = json.load(f)

def save_scores():
    with open(scores_file, "w", encoding="utf-8") as f:
        json.dump(user_scores, f, ensure_ascii=False, indent=2)

with open(questions_file, "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

class QuizView(discord.ui.View):
    def __init__(self, correct_option_index, user_id, asker):
        super().__init__(timeout=30)
        self.correct_option_index = correct_option_index
        self.user_id = user_id
        self.asker = asker
        self.answered = False

    async def handle_answer(self, interaction: discord.Interaction, selected_index):
        if self.answered:
            await interaction.response.send_message("Bu soruya zaten cevap verdiniz.", ephemeral=True)
            return

        self.answered = True
        uid = interaction.user.id
        if uid not in user_scores:
            user_scores[uid] = {"dogru": 0, "yanlis": 0, "cevaplanan": 0}
        user_scores[uid]["cevaplanan"] += 1

        if selected_index == self.correct_option_index:
            user_scores[uid]["dogru"] += 1
            await interaction.response.send_message("✅ Doğru cevap!", ephemeral=True)
        else:
            user_scores[uid]["yanlis"] += 1
            await interaction.response.send_message("❌ Yanlış cevap!", ephemeral=True)

        save_scores()

        button_view = discord.ui.View()
        button_view.add_item(SonrakiSoruButton(uid))
        await interaction.followup.send("🔁 Yeni bir soru denemek ister misin?", view=button_view, ephemeral=True)
        self.stop()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def option_a(self, interaction, button): await self.handle_answer(interaction, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def option_b(self, interaction, button): await self.handle_answer(interaction, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def option_c(self, interaction, button): await self.handle_answer(interaction, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def option_d(self, interaction, button): await self.handle_answer(interaction, 3)

class SonrakiSoruButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="Sonraki Soru", style=discord.ButtonStyle.success)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Bu düğme sana ait değil!", ephemeral=True)
            return
        await send_quiz(interaction)

async def send_quiz(ctx_or_interaction):
    user_id = ctx_or_interaction.user.id if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author.id
    index = user_progress.get(user_id, 0)

    if index >= len(quiz_data):
        msg = "🎉 Tüm soruları cevapladın!"
        await ctx_or_interaction.response.send_message(msg, ephemeral=True) if isinstance(ctx_or_interaction, discord.Interaction) else await ctx_or_interaction.send(msg)
        return

    data = quiz_data[index]
    question = data["question"]
    options = data["options"]
    correct = data["correct"]
    user_progress[user_id] = index + 1

    embed = discord.Embed(title="🧠 Bilgi Yarışması", description=question, color=discord.Color.blue())
    for opt in options:
        embed.add_field(name="\u200b", value=opt, inline=False)
    embed.set_footer(text="⏳ Cevaplamak için 30 saniyen var!")

    view = QuizView(correct_option_index=correct, user_id=user_id, asker=ctx_or_interaction)
    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.response.send_message(embed=embed, view=view)
    else:
        await ctx_or_interaction.send(embed=embed, view=view)

    for i in range(30, 0, -5):
        await asyncio.sleep(5)
        if not view.answered:
            embed.set_footer(text=f"⏳ {i} saniye kaldı!")
            try:
                await ctx_or_interaction.edit_original_response(embed=embed, view=view)
            except:
                pass

    if not view.answered:
        if user_id not in user_scores:
            user_scores[user_id] = {"dogru": 0, "yanlis": 0, "cevaplanan": 0}
        user_scores[user_id]["yanlis"] += 1
        user_scores[user_id]["cevaplanan"] += 1
        save_scores()
        try:
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.followup.send("⏰ Süre doldu!", ephemeral=True)
            else:
                await ctx_or_interaction.send("⏰ Süre doldu!")
        except:
            pass

@bot.tree.command(name="puan-resetle", description="Puanları sıfırlar ve kazananı açıklar (admin komutu).")
async def reset_scores(interaction: discord.Interaction):
    if interaction.user.id not in admin_ids:
        await interaction.response.send_message("⛔ Bu komutu kullanma yetkin yok.", ephemeral=True)
        return

    if not user_scores:
        await interaction.response.send_message("Hiç puan yok!", ephemeral=True)
        return

    winner = max(user_scores.items(), key=lambda x: x[1]["dogru"])
    user = await bot.fetch_user(winner[0])
    dogru = winner[1]["dogru"]
    mesaj = f"🏆 Haftanın kazananı: **{user.name}** — {dogru} doğru cevap!"
    await interaction.response.send_message(mesaj)

    user_scores.clear()
    save_scores()

@bot.tree.command(name="soru-ekle", description="Yeni bir quiz sorusu ekle (admin komutu).")
async def soru_ekle(
    interaction: discord.Interaction,
    soru: str,
    a: str,
    b: str,
    c: str,
    d: str,
    dogru: int
):
    if interaction.user.id not in admin_ids:
        await interaction.response.send_message("⛔ Bu komutu kullanma yetkin yok.", ephemeral=True)
        return

    yeni_soru = {
        "question": soru,
        "options": [f"A) {a}", f"B) {b}", f"C) {c}", f"D) {d}"],
        "correct": dogru
    }

    with open(questions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.append(yeni_soru)
    with open(questions_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    await interaction.response.send_message("✅ Yeni soru eklendi!", ephemeral=True)

@bot.tree.command(name="puan", description="Kendi puanını gösterir.")
async def puan(interaction: discord.Interaction):
    user_id = interaction.user.id
    skor = user_scores.get(user_id, {"dogru": 0, "yanlis": 0, "cevaplanan": 0})
    embed = discord.Embed(title="📊 Puan Durumu", color=discord.Color.green())
    embed.add_field(name="✅ Doğru", value=str(skor["dogru"]))
    embed.add_field(name="❌ Yanlış", value=str(skor["yanlis"]))
    embed.add_field(name="🔢 Toplam", value=str(skor["cevaplanan"]))
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="puan-tablosu", description="Tüm kullanıcıların puanlarını listeler.")
async def puan_tablosu(interaction: discord.Interaction):
    sorted_users = sorted(user_scores.items(), key=lambda x: x[1]["dogru"], reverse=True)
    embed = discord.Embed(title="🏆 Puan Tablosu", color=discord.Color.gold())
    for uid, skor in sorted_users:
        user = await bot.fetch_user(uid)
        embed.add_field(
            name=user.name,
            value=f"✅ {skor['dogru']} | ❌ {skor['yanlis']} | 🔢 {skor['cevaplanan']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="quiz", description="Yeni bir bilgi yarışması sorusu başlatır.")
async def quiz_slash(interaction: discord.Interaction):
    await send_quiz(interaction)

@bot.command(name="quiz")
async def quiz_prefix(ctx):
    await send_quiz(ctx)

@bot.event
async def on_ready():
    load_scores()
    await bot.tree.sync()
    print(f"Bot aktif: {bot.user}")

bot.run(TOKEN)
