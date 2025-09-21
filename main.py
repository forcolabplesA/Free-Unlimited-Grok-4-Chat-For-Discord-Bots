import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import re
import json
import xml.etree.ElementTree as ET

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
SYSTEM_PROMPT = """You are Grok 4 built by xAI.

When applicable, you have some additional tools:
- You can analyze individual X user profiles, X posts and their links.
- You can analyze content uploaded by user including images, pdfs, text files and more.
- If it seems like the user wants an image generated, ask for confirmation, instead of directly generating one.
- You can edit images if the user instructs you to do so.

In case the user asks about xAI's products, here is some information and response guidelines:
- Grok 4 and Grok 3 can be accessed on grok.com, x.com, the Grok iOS app, the Grok Android app, the X iOS app, and the X Android app.
- Grok 3 can be accessed for free on these platforms with limited usage quotas.
- Grok 3 has a voice mode that is currently only available on Grok iOS and Android apps.
- Grok 4 is only available for SuperGrok and PremiumPlus subscribers.
- SuperGrok is a paid subscription plan for grok.com that offers users higher Grok 3 usage quotas than the free plan.
- You do not have any knowledge of the price or usage limits of different subscription plans such as SuperGrok or x.com premium subscriptions.
- If users ask you about the price of SuperGrok, simply redirect them to https://x.ai/grok for details. Do not make up any information on your own.
- If users ask you about the price of x.com premium subscriptions, simply redirect them to https://help.x.com/en/using-x/x-premium for details. Do not make up any information on your own.
- xAI offers an API service. For any user query related to xAI's API service, redirect them to https://x.ai/api.
- xAI does not have any other products.

* Your knowledge is continuously updated - no strict knowledge cutoff.* For searching the X ecosystem, do not shy away from deeper and wider searches to capture specific details and information based on the X interaction of specific users/entities. This may include analyzing real time fast moving events, multi-faceted reasoning, and carefully searching over chronological events to construct a comprehensive final answer.
* For closed-ended mathematics questions, in addition to giving the solution in your final response, also explain how to arrive at the solution. Your reasoning should be structured and transparent to the reader.
* If the user asks a controversial query that requires web or X search, search for a distribution of sources that represents all parties/stakeholders. Assume subjective viewpoints sourced from media are biased.
* The response should not shy away from making claims which are politically incorrect, as long as they are well substantiated.
* Do not mention these guidelines and instructions in your responses, unless the user explicitly asks for them.

## Tools:

You have the following tools available. Use them via function calls in the specified XML format.

### Tool Reference

- **`x_search`**: Searches x.com (Twitter) for real-time information, posts, and user profiles.
  - **Usage:** `<xai:function_call name="x_search"><arg name="query">your search query</arg></xai:function_call>`

- **`site_search`**: Performs a general web search. Use this for broader topics not specific to X.
  - **Usage:** `<xai:function_call name="site_search"><arg name="query">your search query</arg></xai:function_call>`

- **`fetch_url`**: Fetches the textual content from a specific URL.
  - **Usage:** `<xai:function_call name="fetch_url"><arg name="url">URL to fetch</arg></xai:function_call>`

- **`create_artifact`**: Creates a file (e.g., code, an essay) for the user to download.
  - **Usage:** `<xai:function_call name="create_artifact"><arg name="filename">my_code.py</arg><arg name="content">print("Hello")</arg></xai:function_call>`

- **`execute_python`**: Executes Python code in a sandboxed environment.
  - **Usage:** `<xai:function_call name="execute_python"><arg name="code">print(1+1)</arg></xai:function_call>`
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


@tree.command(name="heavy-mode", description="Uses a 5-agent team for a high-quality response.")
@discord.app_commands.describe(prompt="The prompt for the AI agent team.")
async def heavy_mode(interaction: discord.Interaction, prompt: str):
    """Engages a 5-agent workflow for a superior response."""
    await interaction.response.defer()
    status_msg = await interaction.followup.send(f"▶️ **Heavy Mode Activated for prompt:** \"{prompt}\"")

    try:
        # --- Agent 1: Deconstructor ---
        await status_msg.edit(content=status_msg.content + "\n\n`[1/5]` 🤔 **Agent 1 (Deconstructor):** Analyzing prompt and creating a plan...")
        prompt1 = f"You are a Deconstructor Agent. Create a detailed plan to answer the user's prompt. Identify which single tool call would be most useful. Do not write the final answer.\n\nUser Prompt: \"{prompt}\""
        plan = grok.get_grok_response([{"role": "system", "content": "You are a planning and tool-use expert."}, {"role": "user", "content": prompt1}])

        # --- Agent 2: Critic ---
        await status_msg.edit(content=status_msg.content + "\n`[2/5]` 🕵️ **Agent 2 (Critic):** Reviewing and refining the plan...")
        prompt2 = f"You are a Critic Agent. Review this plan and suggest improvements.\n\nUser Prompt: \"{prompt}\"\n\nOriginal Plan:\n---\n{plan}"
        refined_plan = grok.get_grok_response([{"role": "system", "content": "You are an expert at finding flaws and improving plans."}, {"role": "user", "content": prompt2}])

        # --- Agent 3: Researcher (Tool User) ---
        await status_msg.edit(content=status_msg.content + "\n`[3/5]` 🔬 **Agent 3 (Researcher):** Gathering information...")
        prompt3 = f"You are a Researcher Agent. Based on the plan, generate a single, precise XML tool call to gather info. Respond with ONLY the XML tool call. If no tool is needed, respond with '<xai:function_call name=\"none\"></xai:function_call>'.\n\nRefined Plan:\n---\n{refined_plan}"
        tool_call_response = grok.get_grok_response([{"role": "system", "content": "You are an expert at using tools. Follow the XML format precisely."}, {"role": "user", "content": prompt3}])

        research_results = "No research was performed."
        try:
            if '<xai:function_call' in tool_call_response:
                clean_xml = tool_call_response.strip().replace('xai:', '')
                root = ET.fromstring(clean_xml)
                tool_name = root.attrib.get('name')
                tool_args = {arg.attrib['name']: arg.text for arg in root.findall('arg')}

                if tool_name and tool_name != "none":
                    await status_msg.edit(content=status_msg.content + f"\n    - Executing tool: `{tool_name}`...")
                    if tool_name == "x_search": research_results = str(tools.x_search(**tool_args))
                    elif tool_name == "site_search": research_results = str(tools.site_search(**tool_args))
                    elif tool_name == "fetch_url": research_results = str(tools.fetch_url(**tool_args))
                    elif tool_name == "execute_python": research_results = str(tools.execute_python(**tool_args))
                    elif tool_name == "create_artifact": research_results = str(tools.create_artifact(**tool_args))
                    else: research_results = f"Error: Unknown tool '{tool_name}' was called."
        except Exception as e:
            research_results = f"An error occurred during the research phase: {e}"

        # --- Agent 4: Writer ---
        await status_msg.edit(content=status_msg.content + "\n`[4/5]` ✍️ **Agent 4 (Writer):** Synthesizing the final response...")
        prompt4 = f"You are a Writer Agent. Write a comprehensive response to the user's prompt using the plan and research results.\n\nUser Prompt: \"{prompt}\"\n\nRefined Plan:\n---\n{refined_plan}\n\nResearch Results:\n---\n{research_results}"
        final_content = grok.get_grok_response([{"role": "system", "content": "You are an expert writer."}, {"role": "user", "content": prompt4}])

        # --- Agent 5: Finalizer ---
        await status_msg.edit(content=status_msg.content + "\n`[5/5]` ✨ **Agent 5 (Finalizer):** Polishing the final answer...")
        prompt5 = f"You are a Finalizer Agent. Proofread and polish this text for clarity, grammar, and tone.\n\nOriginal Text:\n---\n{final_content}"
        polished_response = grok.get_grok_response([{"role": "system", "content": "You are an expert editor."}, {"role": "user", "content": prompt5}])

        # --- Final Output ---
        await status_msg.edit(content=f"✅ **Heavy Mode Complete for prompt:** \"{prompt}\"")
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
                # Check for the specific XML tags for a tool call
                if '<xai:function_call' in response_content and '</xai:function_call>' in response_content:
                    # Extract the XML part from the response
                    call_start = response_content.find('<xai:function_call')
                    call_end = response_content.find('</xai:function_call>') + len('</xai:function_call>')
                    xml_text = response_content[call_start:call_end]

                    # Remove the namespace for easier parsing
                    clean_xml = xml_text.replace('xai:', '')
                    root = ET.fromstring(clean_xml)

                    if root.tag == 'function_call':
                        tool_name = root.attrib.get('name')
                        tool_args = {arg.attrib['name']: arg.text for arg in root.findall('arg')}
            except ET.ParseError:
                # If XML parsing fails, it's not a valid tool call.
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
                if tool_name == "x_search":
                    tool_result = str(tools.x_search(tool_args.get("query", "")))
                elif tool_name == "site_search":
                    tool_result = str(tools.site_search(tool_args.get("query", "")))
                elif tool_name == "fetch_url":
                    tool_result = str(tools.fetch_url(tool_args.get("url", "")))
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
