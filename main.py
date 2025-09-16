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
public_chat_channels = set() # For /setchat command
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

@tree.command(name="setchat", description="Sets the current channel as a public chat for the bot.")
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def setchat(interaction: discord.Interaction):
    """Sets the current channel for public bot interaction."""
    channel_id = interaction.channel.id
    if channel_id in public_chat_channels:
        await interaction.response.send_message("This channel is already set as a public chat.", ephemeral=True)
    else:
        public_chat_channels.add(channel_id)
        # Add the bot to the conversation history so it can introduce itself
        conversation_histories[channel_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        await interaction.response.send_message(f"This channel ({interaction.channel.mention}) is now a public chat. I will respond to all messages here.")

@tree.command(name="unsetchat", description="Removes the bot from this public chat channel.")
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def unsetchat(interaction: discord.Interaction):
    """Removes the bot from the public chat channel."""
    channel_id = interaction.channel.id
    if channel_id in public_chat_channels:
        public_chat_channels.discard(channel_id)
        # Optionally, clear the conversation history for that channel
        if channel_id in conversation_histories:
            del conversation_histories[channel_id]
        await interaction.response.send_message(f"I will no longer respond to messages in this channel.")
    else:
        await interaction.response.send_message("This channel is not set as a public chat.", ephemeral=True)

@setchat.error
@unsetchat.error
async def on_chat_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"An unexpected error occurred: {error}", ephemeral=True)


@tree.command(name="heavy-mode", description="Uses a 4-agent team for a high-quality response.")
@discord.app_commands.describe(prompt="The prompt for the AI agent team.")
async def heavy_mode(interaction: discord.Interaction, prompt: str):
    """Engages a multi-agent workflow for a superior response."""
    await interaction.response.defer()

    # Send an initial message that will be updated with the progress
    status_msg = await interaction.followup.send(f"▶️ **Heavy Mode Activated for prompt:** \"{prompt}\"")

    try:
        # --- Agent 1: The Outliner ---
        await status_msg.edit(content=status_msg.content + "\n\n`[1/4]` 🤔 **Agent 1 (Outliner):** Generating a plan...")
        prompt1 = f"You are an expert Outliner. Create a detailed plan to answer the user's prompt. Do not write the answer, just the outline.\n\nUser Prompt: \"{prompt}\""
        outline = grok.get_grok_response([{"role": "user", "content": prompt1}])

        # --- Agent 2: The Critic ---
        await status_msg.edit(content=status_msg.content + f"\n`[2/4]` 🕵️ **Agent 2 (Critic):** Reviewing the plan...")
        prompt2 = f"You are an expert Critic. Review this plan and suggest improvements. Identify weaknesses and missing information.\n\nUser Prompt: \"{prompt}\"\n\nOriginal Plan:\n---\n{outline}"
        refined_plan = grok.get_grok_response([{"role": "user", "content": prompt2}])

        # --- Agent 3: The Writer ---
        await status_msg.edit(content=status_msg.content + f"\n`[3/4]` ✍️ **Agent 3 (Writer):** Writing the final response...")
        prompt3 = f"You are an expert Writer. Write a comprehensive response to the user's prompt using the refined plan below.\n\nUser Prompt: \"{prompt}\"\n\nRefined Plan:\n---\n{refined_plan}"
        final_content = grok.get_grok_response([{"role": "user", "content": prompt3}])

        # --- Agent 4: The Editor ---
        await status_msg.edit(content=status_msg.content + f"\n`[4/4]` ✨ **Agent 4 (Editor):** Polishing the final response...")
        prompt4 = f"You are an expert Editor. Proofread and polish this text for clarity, grammar, and tone.\n\nOriginal Text:\n---\n{final_content}"
        polished_response = grok.get_grok_response([{"role": "user", "content": prompt4}])

        # --- Final Output ---
        await status_msg.edit(content=f"✅ **Heavy Mode Complete for prompt:** \"{prompt}\"")
        # Send the final response, pinging the user who started the command
        await interaction.followup.send(f"{interaction.user.mention}\n\n{polished_response}", suppress_embeds=True)

    except Exception as e:
        await status_msg.edit(content=f"❌ **Heavy Mode Failed for prompt:** \"{prompt}\"\n\nAn error occurred: {e}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_private_chat = message.channel.id in private_chat_channels
    is_public_chat = message.channel.id in public_chat_channels

    if not is_dm and not is_private_chat and not is_public_chat:
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

    # Use a thinking message that is not a reply, so we can reply with the final answer.
    thinking_msg = await message.channel.send("Thinking...")
    thinking_task = asyncio.create_task(thinking_animation(thinking_msg))
    response_content = ""

    try:
        # Initialize conversation history if it's the first message in the channel
        if channel_id not in conversation_histories:
            current_system_prompt = SYSTEM_PROMPT
            if message.guild:
                emojis = message.guild.emojis[:30]
                if emojis:
                    emoji_list_str = "\n".join([f"- {str(e)} (`{e.name}`)" for e in emojis])
                    emoji_prompt_section = (
                        "\n\n## Custom Emoji Instructions\n"
                        "This server has custom emojis. To use one, include its full code in your response (e.g., `<:example:12345>`).\n"
                        "Available emojis:\n"
                        f"{emoji_list_str}"
                    )
                    current_system_prompt += emoji_prompt_section
            conversation_histories[channel_id] = [{"role": "system", "content": current_system_prompt}]

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
                        tool_name = None
            except (json.JSONDecodeError, TypeError):
                pass

            if tool_name:
                conversation_histories[channel_id].append({"role": "assistant", "content": response_content})

                if tool_name == "create_artifact":
                    filename = tool_args.get("filename")
                    content = tool_args.get("content")
                    result_msg = tools.create_artifact(filename, content)
                    if "Success" in result_msg:
                        filepath = os.path.join("artifacts", filename)
                        try:
                            await message.reply(file=discord.File(filepath))
                            tool_feedback = f"Successfully created and sent artifact '{filename}'."
                        except Exception as e:
                            tool_feedback = f"Failed to send artifact '{filename}': {e}"
                    else:
                        tool_feedback = result_msg
                    conversation_histories[channel_id].append({"role": "tool", "content": tool_feedback})
                    continue

                tool_result = ""
                if tool_name == "web_search":
                    tool_result = str(tools.web_search(tool_args.get("query", "")))
                elif tool_name == "execute_python":
                    tool_result = tools.execute_python(tool_args.get("code", ""))
                else:
                    tool_result = f"Error: Unknown tool '{tool_name}'."
                conversation_histories[channel_id].append({"role": "tool", "content": tool_result})
                continue
            else:
                break

        conversation_histories[channel_id].append({"role": "assistant", "content": response_content})

    except Exception as e:
        print(f"An error occurred during conversation: {e}")
        response_content = "Sorry, a critical error occurred."
    finally:
        thinking_task.cancel()
        await thinking_msg.delete()

    if response_content:
        await message.reply(response_content)

def main():
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
        print("Error: DISCORD_BOT_TOKEN is not set in the .env file.")
        return
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
