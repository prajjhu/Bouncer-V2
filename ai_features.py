import state


async def build_bouncer_context(channel, limit=8):
    msgs = []
    try:
        async for msg in channel.history(limit=limit):
            if msg.author.bot and msg.author != state.client.user:
                continue
            author = "Bouncer" if msg.author == state.client.user else msg.author.display_name
            msgs.append(f"{author}: {msg.content}")
    except:
        return ""
    msgs.reverse()
    return "\n".join(msgs)


async def bouncer_ai_reply(message):
    try:
        chat_context = await build_bouncer_context(message.channel)
        res = await state.client_ai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Bouncer, the chill late-night club bouncer of a Discord server called Plan B. "
                        "Moderation is currently paused, so you are only here to reply like a smart, socially aware human. "
                        "Be concise, natural, witty when it fits, and reply based on the current chat context. "
                        "Do not act like an assistant giving essays unless asked."
                    )
                },
                {
                    "role": "user",
                    "content": f"Recent chat:\n{chat_context}\n\nReply to this message naturally:\n{message.author.display_name}: {message.content}"
                }
            ]
        )
        sent = await message.reply(res.choices[0].message.content[:2000], mention_author=False)
        state.standby_bot_messages.append(sent)
    except Exception as e:
        print("BOUNCER REPLY ERROR:", e)


async def clear_standby_messages():
    for msg in state.standby_bot_messages:
        try:
            await msg.delete()
        except:
            pass
    state.standby_bot_messages = []


async def analyze(uid, text, use_context=True):
    try:
        context_text = ""
        if use_context:
            history = state.user_context.get(uid, [])
            context_text = "\n".join(history[:-1])

        prompt = f"""
Previous messages:
{context_text}

Current message:
{text}
"""

        res = await state.client_ai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a moderation AI for a chill social Discord server.\n\n"
                        "SAFE = casual language, jokes, slang, swearing\n"
                        "MEDIUM = repeated or targeted insults\n"
                        "HIGH = clear threats, hate speech, or serious harassment\n\n"
                        "IMPORTANT RULES:\n"
                        "- Do NOT punish casual swearing\n"
                        "- Do NOT punish friendly banter\n"
                        "- Do NOT overreact to single messages\n"
                        "- Only escalate if behavior is clearly repeated or harmful\n"
                        "- Only return HIGH if it is serious and intentional\n\n"
                        "Return ONLY: SAFE, MEDIUM, HIGH"
                    )
                },
                {"role": "user", "content": prompt}
            ]
        )
        return res.choices[0].message.content.strip()
    except:
        return "SAFE"
