import os
import time
import random
import discord

import state
from config import PREFIX, JAIL_CHANNELS, AI_CHANNEL_NAME, CONSOLE_CHANNEL_NAME, AI_STRIKE_DECAY, CONTEXT_LIMIT, TRIGGERS, BANNED
from helpers import (
    normalize_text,
    contains_discord_invite,
    is_invite_allowed_channel,
    is_console_channel,
    is_console_authorized,
    add_recent_action,
    build_status_embed,
    build_recent_actions_embed,
    build_user_check_embed,
    has_severe_target_phrase,
    bot_reply,
    is_similar,
)
from ai_features import bouncer_ai_reply, clear_standby_messages, analyze
from moderation import cleanup_spam, cleanup_recent_spam, log_action, jail_user, handle_targeted_harassment, decay_pair_state
from console import ConsolePanel

NORMALIZED_BANNED = [normalize_text(w) for w in BANNED]


@state.client.event
async def on_ready():
    if not state.panel_registered:
        state.client.add_view(ConsolePanel())
        state.panel_registered = True
    print(f"Logged in as {state.client.user}")


@state.client.event
async def on_message(message):
    if message.author == state.client.user:
        return

    uid = str(message.author.id)
    content = message.content.lower()
    normalized = normalize_text(content)
    now = time.time()

    last = state.user_last_seen.get(uid, now)
    if now - last > AI_STRIKE_DECAY:
        state.user_medium_strikes[uid] = max(0, state.user_medium_strikes.get(uid, 0) - 1)
        state.user_high_strikes[uid] = max(0, state.user_high_strikes.get(uid, 0) - 1)
    state.user_last_seen[uid] = now
    decay_pair_state(now)

    state.user_context.setdefault(uid, []).append(message.content)
    if len(state.user_context[uid]) > CONTEXT_LIMIT:
        state.user_context[uid].pop(0)

    if content.startswith(PREFIX + "release"):
        if message.author.guild_permissions.administrator and message.mentions:
            user = message.mentions[0]
            role = discord.utils.get(message.guild.roles, name="Jailed")
            if role:
                await user.remove_roles(role)
            state.user_medium_strikes.pop(str(user.id), None)
            state.user_high_strikes.pop(str(user.id), None)
            await log_action(message.guild, "🔓 Released", f"{user.mention}")
            add_recent_action(f"{user.display_name} released")
            await message.channel.send(f"{user.mention} released", delete_after=5)
            try:
                await message.delete()
            except:
                pass
        return

    if is_console_channel(message.channel) and is_console_authorized(message.author):
        if content.startswith(PREFIX + "status"):
            await message.channel.send(embed=build_status_embed(message.guild), delete_after=20)
            return
        if content.startswith(PREFIX + "check") and message.mentions:
            await message.channel.send(embed=build_user_check_embed(message.mentions[0]), delete_after=20)
            return
        if content.startswith(PREFIX + "recentactions"):
            await message.channel.send(embed=build_recent_actions_embed(), delete_after=20)
            return
        if content.startswith(PREFIX + "clearbotmsgs"):
            count = 0
            async for msg in message.channel.history(limit=50):
                if msg.author == state.client.user and msg.id != message.id:
                    try:
                        await msg.delete()
                        count += 1
                    except:
                        pass
            add_recent_action(f"{message.author.display_name} cleared {count} bot messages")
            await message.channel.send(f"cleared {count} bot messages", delete_after=5)
            return
        if content.startswith(PREFIX + "panel"):
            embed = discord.Embed(
                title="Plan B Guardian Console",
                description=(
                    "Staff/Admin control panel for the bot.\n\n"
                    "Buttons:\n"
                    "• Status\n"
                    "• Standby\n"
                    "• Resume\n"
                    "• Recent\n"
                    "• Clear Bot Msgs"
                ),
                color=discord.Color.from_rgb(135, 70, 190)
            )
            embed.set_footer(text=f"Console works only in #{CONSOLE_CHANNEL_NAME}")
            await message.channel.send(embed=embed, view=ConsolePanel())
            return

    if content.startswith(PREFIX + "standby"):
        if message.author.guild_permissions.administrator:
            state.moderation_enabled = False
            add_recent_action(f"{message.author.display_name} enabled standby")
            await message.channel.send("moderation standby enabled 💤", delete_after=5)
            try:
                await message.delete()
            except:
                pass
        return

    if content.startswith(PREFIX + "resume"):
        if message.author.guild_permissions.administrator:
            state.moderation_enabled = True
            await clear_standby_messages()
            add_recent_action(f"{message.author.display_name} resumed moderation")
            await message.channel.send("moderation resumed ✅", delete_after=5)
            try:
                await message.delete()
            except:
                pass
        return

    if uid in state.invite_ad_warning_times and now - state.invite_ad_warning_times[uid] > 10:
        state.invite_ad_warning_times.pop(uid, None)
        if uid in state.invite_ad_warnings:
            state.invite_ad_warnings.remove(uid)

    if contains_discord_invite(message.content):
        if not message.author.guild_permissions.administrator and not is_invite_allowed_channel(message.channel):
            await message.delete()
            if uid not in state.invite_ad_warnings:
                state.invite_ad_warnings.append(uid)
                state.invite_ad_warning_times[uid] = now
                add_recent_action(f"{message.author.display_name} warned for invite advertising")
                await message.channel.send(
                    f"{message.author.mention}, Do not Advertise your server in these chat, Visit Partnerships, repeated offense will result in Jail-time",
                    delete_after=8
                )
            else:
                await message.channel.send(f"{message.author.mention} warned already.", delete_after=5)
                await message.channel.send(bot_reply("jail"), delete_after=5)
                await jail_user(message.author, message.guild, "Discord invite advertising", message.channel)
                state.invite_ad_warnings.remove(uid)
                state.invite_ad_warning_times.pop(uid, None)
            return

    if message.channel.name in JAIL_CHANNELS:
        return

    # --- UPDATED: Bouncer always-on with 15s per-user cooldown ---
    if "bouncer" in content:
        last_bounce = state.bouncer_cooldowns.get(uid, 0)
        if now - last_bounce >= 15:
            state.bouncer_cooldowns[uid] = now
            await bouncer_ai_reply(message)
            return

    if not state.moderation_enabled:
        if state.client.user in message.mentions:
            return

    if state.moderation_enabled and state.client.user in message.mentions:
        await message.channel.send(random.choice([
            "yeah i'm watching 👀",
            "all systems running",
            "i see everything",
            "nothing escapes me",
            "you good?"
        ]), delete_after=5)
        return

    if content.startswith(PREFIX + "chat"):
        if AI_CHANNEL_NAME not in message.channel.name:
            await message.channel.send("Go to #ai-chat 🤖", delete_after=5)
            return
        role = discord.utils.get(message.guild.roles, name="AI Access")
        if role not in message.author.roles:
            await message.channel.send("you don't have access to AI chat, dm @ap.snake 🔐", delete_after=5)
            return
        prompt = message.content[len(PREFIX + "chat"):].strip()
        res = await state.client_ai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Talk like a chill Gen Z human."},
                {"role": "user", "content": prompt}
            ]
        )
        sent = await message.channel.send(res.choices[0].message.content[:2000])
        if not state.moderation_enabled:
            state.standby_bot_messages.append(sent)
        return

    if not state.moderation_enabled:
        return

    if any(b in normalized for b in NORMALIZED_BANNED):
        await message.delete()
        await cleanup_spam(message.channel, message.author, content)
        await message.channel.send(bot_reply("jail"), delete_after=5)
        await jail_user(message.author, message.guild, "Banned word", message.channel)
        return

    handled = await handle_targeted_harassment(message, now)
    if handled:
        return

    state.user_message_times.setdefault(uid, []).append(now)
    state.user_message_times[uid] = [t for t in state.user_message_times[uid] if now - t < 3]
    if len(state.user_message_times[uid]) >= 7:
        await cleanup_recent_spam(message.channel, message.author)
        await message.channel.send("bro relax 💀", delete_after=5)
        await jail_user(message.author, message.guild, "Raid spam", message.channel)
        return

    if len(content) > 5:
        use_context = any(w in content for w in TRIGGERS)
        result = await analyze(uid, message.content, use_context)
        if result == "SAFE":
            state.user_medium_strikes[uid] = max(0, state.user_medium_strikes.get(uid, 0) - 1)
            state.user_high_strikes[uid] = max(0, state.user_high_strikes.get(uid, 0) - 1)
            return
        if result == "MEDIUM":
            s = state.user_medium_strikes.get(uid, 0) + 1
            state.user_medium_strikes[uid] = min(s, 3)
            return
        if result == "HIGH":
            if has_severe_target_phrase(message.content):
                await message.channel.send(bot_reply("jail"), delete_after=5)
                await jail_user(message.author, message.guild, "Severe behavior", message.channel)
                state.user_high_strikes[uid] = 0
                return
            s = state.user_high_strikes.get(uid, 0) + 1
            state.user_high_strikes[uid] = s
            if s == 2:
                add_recent_action(f"{message.author.display_name} warned for high-risk behavior")
                await message.channel.send("enough", delete_after=4)
                return
            if s >= 3:
                await message.channel.send(bot_reply("jail"), delete_after=5)
                await jail_user(message.author, message.guild, "Severe behavior", message.channel)
                state.user_high_strikes[uid] = 0
                return

    last = state.user_last_content.get(uid)
    if last and is_similar(last, content):
        state.user_repeat_count[uid] = state.user_repeat_count.get(uid, 0) + 1
    else:
        state.user_last_content[uid] = content
        state.user_repeat_count[uid] = 1

    if state.user_repeat_count[uid] >= 5:
        await cleanup_recent_spam(message.channel, message.author)
        await message.channel.send(bot_reply("jail"), delete_after=5)
        await jail_user(message.author, message.guild, "Spam", message.channel)
        return


state.client.run(os.getenv("TOKEN"))
