import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import re
import json

import grok
import tools

# --- Environment and Bot Setup ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- System Prompts and Data ---
SYSTEM_PROMPT = """You are a powerful AI assistant in a Discord bot. You have tools to help users.

When you need a tool, respond ONLY with a JSON object where the key is the tool name and the value is the arguments object.

Available Tools & Format Examples:
1. `web_search`: `{"web_search": {"query": "latest AI news"}}`
2. `create_artifact`: `{"create_artifact": {"filename": "story.txt", "content": "Once upon a time..."}}`
3. `execute_python`: `{"execute_python": {"code": "print(1 + 1)"}}`

Tool Use Flow:
1. User sends a message.
2. If a tool is needed, you respond with the tool's JSON.
3. The system will execute the tool and return the result to you in a message with `role: "tool"`.
4. You then formulate the final response to the user based on the tool's output.

If no tool is needed, just respond to the user directly in plain text.
"""

conversation_histories = {}
private_chat_channels = set()
channels_to_be_renamed = set()
new_chat_counter = 1

# --- Helper Functions ---
async def thinking_animation(message):
    dots = 1
    try:
        while True:
            await message.edit(content=f"Thinking{'.' * dots}")
            dots = (dots % 3) + 1
            await asyncio.sleep(1)
    except (discord.errors.NotFound, asyncio.CancelledError):
        pass

def sanitize_channel_name(name: str) -> str:
    name = name.lower().strip().replace(" ", "-")
    name = re.sub(r'[^a-z0-9-]', '', name)
    return name[:100] or "new-chat"

# --- Bot Events and Commands ---
@bot.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@tree.command(name="start", description="Starts a new private chat with the bot.")
async def start(interaction: discord.Interaction):
    global new_chat_counter
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    user = interaction.user
    if not guild.me.guild_permissions.manage_channels:
        await interaction.followup.send("I don't have permission to create channels.")
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    channel_name = f"new-chat-{new_chat_counter}"
    try:
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=interaction.channel.category)
        new_chat_counter += 1
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")
        return
    private_chat_channels.add(channel.id)
    channels_to_be_renamed.add(channel.id)
    await interaction.followup.send(f"I've created a private channel for you: {channel.mention}")
    await channel.send(f"Hello {user.mention}! This is our private chat. What can I help you with?")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_private_chat = message.channel.id in private_chat_channels

    if not is_dm and not is_private_chat:
        return

    channel_id = message.channel.id

    if channel_id in channels_to_be_renamed and not is_dm:
        rename_prompt = [{"role": "system", "content": "Generate a short, descriptive, kebab-case channel name (2-5 words) for a conversation starting with this message."}, {"role": "user", "content": message.content}]
        try:
            new_name_raw = grok.get_grok_response(rename_prompt)
            new_name = sanitize_channel_name(new_name_raw)
            await message.channel.edit(name=new_name)
            channels_to_be_renamed.remove(channel_id)
        except Exception as e:
            print(f"Could not rename channel {channel_id}: {e}")
            channels_to_be_renamed.remove(channel_id)

    thinking_msg = await message.channel.send("Thinking...")
    thinking_task = asyncio.create_task(thinking_animation(thinking_msg))

    try:
        if channel_id not in conversation_histories:
            conversation_histories[channel_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        conversation_histories[channel_id].append({"role": "user", "content": message.content})

        while True:
            response_content = grok.get_grok_response(conversation_histories[channel_id])

            tool_name, tool_args = None, None
            try:
                tool_call = json.loads(response_content)
                if isinstance(tool_call, dict) and len(tool_call) == 1:
                    tool_name = list(tool_call.keys())[0]
                    tool_args = tool_call[tool_name]
                    if not isinstance(tool_args, dict):
                        tool_name = None # Not a valid tool call structure
            except (json.JSONDecodeError, TypeError):
                pass # Not a JSON, so it's a final response

            if tool_name:
                conversation_histories[channel_id].append({"role": "assistant", "content": response_content})

                if tool_name == "web_search":
                    tool_result = str(tools.web_search(tool_args.get("query", "")))
                    conversation_histories[channel_id].append({"role": "tool", "content": tool_result})
                    continue
                elif tool_name == "execute_python":
                    tool_result = tools.execute_python(tool_args.get("code", ""))
                    conversation_histories[channel_id].append({"role": "tool", "content": tool_result})
                    continue
                elif tool_name == "create_artifact":
                    filename = tool_args.get("filename")
                    content = tool_args.get("content")
                    result_msg = tools.create_artifact(filename, content)

                    if "Success" in result_msg:
                        filepath = os.path.join("artifacts", filename)
                        try:
                            await message.channel.send(file=discord.File(filepath))
                            tool_feedback = f"Successfully created and sent artifact '{filename}'."
                        except Exception as e:
                            tool_feedback = f"Failed to send artifact '{filename}': {e}"
                    else:
                        tool_feedback = result_msg

                    conversation_histories[channel_id].append({"role": "tool", "content": tool_feedback})
                    continue
                else:
                    conversation_histories[channel_id].append({"role": "tool", "content": f"Error: Unknown tool '{tool_name}'."})
                    continue
            else:
                # Not a tool call, break the loop
                break

        conversation_histories[channel_id].append({"role": "assistant", "content": response_content})
    except Exception as e:
        print(f"An error occurred during conversation: {e}")
        response_content = "Sorry, a critical error occurred."
    finally:
        thinking_task.cancel()
        await thinking_msg.delete()

    if response_content:
        await message.channel.send(response_content)

def main():
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        print("Error: DISCORD_BOT_TOKEN is not set in the .env file.")
        return
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
