import time
import discord

import state
from config import LOG_CHANNEL_NAME, MODERATOR_ROLE_NAME, JAIL_CHANNELS, TARGET_WINDOW, WARNING_DECAY
from helpers import (
    is_similar,
    bot_reply,
    add_recent_action,
    get_target_id,
    has_severe_target_phrase,
    has_direct_target_phrase,
    has_light_hostility,
    is_exit_line,
)


def decay_pair_state(now):
    expired_pairs = []
    for pair, last_time in state.pair_last_time.items():
        if now - last_time > TARGET_WINDOW:
            expired_pairs.append(pair)
    for pair in expired_pairs:
        state.pair_hostility.pop(pair, None)
        state.pair_last_time.pop(pair, None)

    expired_warns = []
    for pair, warned_at in state.pair_warned.items():
        if now - warned_at > WARNING_DECAY:
            expired_warns.append(pair)
    for pair in expired_warns:
        state.pair_warned.pop(pair, None)


async def cleanup_spam(channel, user, ref, limit=30):
    def check(msg):
        return msg.author == user and is_similar(msg.content.lower(), ref.lower())
    try:
        await channel.purge(limit=limit, check=check)
    except:
        pass


async def cleanup_recent_spam(channel, user, limit=30):
    recent = []
    try:
        async for msg in channel.history(limit=limit):
            if msg.author == user:
                recent.append(msg)
    except:
        return

    recent.reverse()
    spam_msgs = []
    last_text = None
    streak = 0
    for msg in recent:
        text = msg.content.strip().lower()
        if not text:
            continue
        if last_text and is_similar(last_text, text):
            streak += 1
        else:
            streak = 1
        if streak >= 2:
            spam_msgs.append(msg)
        last_text = text

    for msg in spam_msgs:
        try:
            await msg.delete()
        except:
            pass


async def log_action(guild, title, desc):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if ch:
        embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)


async def notify_mods_jail(channel, guild, member, reason, trigger=None):
    role = discord.utils.get(guild.roles, name=MODERATOR_ROLE_NAME)
    if not role:
        print(f"MOD ALERT ERROR: role '{MODERATOR_ROLE_NAME}' not found")
        return
    trigger_text = f"\nMessage: \"{trigger}\"" if trigger else ""
    try:
        await channel.send(
            f"{role.mention} {member.mention} has been jailed, due to: {reason}{trigger_text}",
            allowed_mentions=discord.AllowedMentions(roles=True, users=True),
            delete_after=10
        )
    except Exception as e:
        print("MOD ALERT ERROR:", e)


async def jail_user(member, guild, reason, source_channel=None, trigger=None):
    uid = str(member.id)
    now = time.time()
    if uid in state.user_jail_lock and now - state.user_jail_lock[uid] < 3:
        return
    state.user_jail_lock[uid] = now

    role = discord.utils.get(guild.roles, name="Jailed")
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

    trigger_text = f"\nMessage: \"{trigger}\"" if trigger else ""
    await log_action(guild, "🚨 User Jailed", f"{member.mention}\nReason: {reason}{trigger_text}")
    add_recent_action(f"{member.display_name} jailed - {reason}")

    if source_channel:
        await notify_mods_jail(source_channel, guild, member, reason, trigger)

    jail_channel = None
    for ch in guild.text_channels:
        if any(name in ch.name for name in JAIL_CHANNELS):
            jail_channel = ch
            break

    if jail_channel:
        try:
            await jail_channel.send(
                f"🚨 {member.mention} was jailed\nReason: {reason}{trigger_text}",
                delete_after=60
            )
        except Exception as e:
            print("JAIL MESSAGE ERROR:", e)


async def handle_targeted_harassment(message, now):
    uid = str(message.author.id)
    target_id = get_target_id(message)
    if not target_id or target_id == uid:
        return False

    content = message.content.lower()
    pair = (uid, target_id)
    reverse_pair = (target_id, uid)

    if has_severe_target_phrase(message.content):
        await message.channel.send(bot_reply("jail"), delete_after=5)
        await jail_user(message.author, message.guild, "Severe targeted harassment", message.channel, trigger=message.content)
        state.pair_hostility.pop(pair, None)
        state.pair_last_time.pop(pair, None)
        state.pair_warned.pop(pair, None)
        return True

    direct = has_direct_target_phrase(content) or bool(message.mentions) or bool(message.reference)
    light = has_light_hostility(content)
    exit_line = is_exit_line(content)
    if not direct and not light:
        return False

    last_time = state.pair_last_time.get(pair, 0)
    if now - last_time > TARGET_WINDOW:
        state.pair_hostility[pair] = 0

    score = state.pair_hostility.get(pair, 0)
    if exit_line:
        score = max(0, score - 1)
    elif direct and light:
        score += 1.25
    elif direct:
        score += 0.75
    elif light:
        score += 0.5

    state.pair_hostility[pair] = min(score, 6)
    state.pair_last_time[pair] = now

    reverse_active = reverse_pair in state.pair_last_time and now - state.pair_last_time.get(reverse_pair, 0) <= TARGET_WINDOW
    reverse_score = state.pair_hostility.get(reverse_pair, 0)
    is_mutual = reverse_active and reverse_score >= 1.5

    if exit_line:
        return False
    if is_mutual and score < 5:
        return False

    warned_at = state.pair_warned.get(pair)
    if score >= 3 and warned_at is None:
        state.pair_warned[pair] = now
        add_recent_action(f"{message.author.display_name} soft-warned for repeated targeting")
        await message.channel.send("keep it chill", delete_after=4)
        return True

    if score >= 5 and warned_at and now - warned_at <= WARNING_DECAY:
        add_recent_action(f"{message.author.display_name} jailed for repeated targeted harassment")
        await message.channel.send(bot_reply("jail"), delete_after=5)
        await jail_user(message.author, message.guild, "Repeated targeted harassment", message.channel, trigger=message.content)
        state.pair_hostility.pop(pair, None)
        state.pair_last_time.pop(pair, None)
        state.pair_warned.pop(pair, None)
        return True

    return False
