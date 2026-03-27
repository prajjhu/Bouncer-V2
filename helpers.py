import re
import datetime
import random
import discord
from difflib import SequenceMatcher

import state
from config import (
    SIMILARITY_THRESHOLD,
    ALLOWED_INVITE_CHANNELS,
    CONSOLE_CHANNEL_NAME,
    MODERATOR_ROLE_NAME,
    DIRECT_TARGET_PHRASES,
    LIGHT_HOSTILITY_WORDS,
    SEVERE_TARGET_PHRASES,
    EXIT_PHRASES,
)


def bot_reply(level):
    return random.choice({
        "warn": ["easy there 😅", "chill a bit bro", "not that serious", "watch it 👀"],
        "serious": ["yeah that crossed the line", "nah we don’t do that here", "alright that’s enough", "you’re pushing it now"],
        "jail": ["yeah… you earned that one", "straight to jail 💀", "nah take a break", "you did that to yourself fr"]
    }[level])


def warn_user(member, level):
    if level == "medium":
        return f"⚠️ {member.mention} chill a bit"
    if level == "high":
        return f"🚨 {member.mention} that’s too far"


def normalize_text(text):
    text = text.lower()
    replacements = {"@": "a", "4": "a", "0": "o", "1": "i", "3": "e", "$": "s", "!": "i"}
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r'[\W_]+', '', text)
    text = re.sub(r'(.)\1+', r'\1', text)
    return text


def is_similar(a, b):
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD


def contains_discord_invite(text):
    pattern = r'(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+'
    return re.search(pattern, text, re.IGNORECASE) is not None


def is_invite_allowed_channel(channel):
    return channel.name in ALLOWED_INVITE_CHANNELS


def is_console_channel(channel):
    return channel.name == CONSOLE_CHANNEL_NAME


def is_console_authorized(member):
    if member.guild_permissions.administrator:
        return True
    role = discord.utils.get(member.guild.roles, name=MODERATOR_ROLE_NAME)
    return role in member.roles if role else False


def add_recent_action(text):
    stamp = datetime.datetime.utcnow().strftime("%H:%M:%S")
    state.recent_actions.append(f"[{stamp}] {text}")
    if len(state.recent_actions) > 20:
        state.recent_actions.pop(0)


def build_status_embed(guild):
    embed = discord.Embed(title="Bot Console Status", color=discord.Color.from_rgb(135, 70, 190))
    embed.add_field(name="Moderation", value="Enabled ✅" if state.moderation_enabled else "Standby 💤", inline=True)
    embed.add_field(name="Invite Filter", value="Enabled ✅", inline=True)
    embed.add_field(name="Standby Replies", value=str(len(state.standby_bot_messages)), inline=True)
    embed.add_field(name="Invite Warnings", value=str(len(state.invite_ad_warnings)), inline=True)
    embed.add_field(name="Recent Actions", value=str(len(state.recent_actions)), inline=True)
    embed.add_field(name="Console Channel", value=f"#{CONSOLE_CHANNEL_NAME}", inline=True)
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_recent_actions_embed():
    embed = discord.Embed(title="Recent Bot Actions", color=discord.Color.blurple())
    embed.description = "\n".join(state.recent_actions[-10:]) if state.recent_actions else "No recent actions."
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_user_check_embed(member):
    uid = str(member.id)
    embed = discord.Embed(title=f"Check: {member.display_name}", color=discord.Color.orange())
    embed.add_field(name="Medium Strikes", value=str(state.user_medium_strikes.get(uid, 0)), inline=True)
    embed.add_field(name="High Strikes", value=str(state.user_high_strikes.get(uid, 0)), inline=True)
    embed.add_field(name="Repeat Count", value=str(state.user_repeat_count.get(uid, 0)), inline=True)
    embed.add_field(name="Invite Warning", value="Yes" if uid in state.invite_ad_warnings else "No", inline=True)
    embed.add_field(name="Jail Lock", value="Yes" if uid in state.user_jail_lock else "No", inline=True)
    embed.add_field(name="Recent Context", value=" | ".join(state.user_context.get(uid, [])[-1:]) or "None", inline=False)
    embed.timestamp = discord.utils.utcnow()
    return embed


def get_target_id(message):
    for user in message.mentions:
        if not user.bot:
            return str(user.id)
    if message.reference and getattr(message.reference, "resolved", None):
        ref = message.reference.resolved
        if getattr(ref, "author", None) and not ref.author.bot:
            return str(ref.author.id)
    return None


def is_exit_line(text):
    t = text.lower()
    return any(p in t for p in EXIT_PHRASES)


def has_light_hostility(text):
    t = text.lower()
    return any(w in t for w in LIGHT_HOSTILITY_WORDS)


def has_direct_target_phrase(text):
    t = text.lower()
    return any(p in t for p in DIRECT_TARGET_PHRASES)


def has_severe_target_phrase(text):
    t = normalize_text(text)
    severe_normalized = [normalize_text(x) for x in SEVERE_TARGET_PHRASES]
    return any(p in t for p in severe_normalized)
