import os
import discord
from openai import AsyncOpenAI

client_ai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

user_message_times = {}
user_last_content = {}
user_repeat_count = {}
user_medium_strikes = {}
user_high_strikes = {}
user_jail_lock = {}
user_context = {}
user_last_seen = {}
recent_toxic_users = {}
moderation_enabled = True
standby_bot_messages = []
invite_ad_warnings = []
invite_ad_warning_times = {}
recent_actions = []
panel_registered = False
pair_hostility = {}
pair_last_time = {}
pair_warned = {}
bouncer_cooldowns = {}
