import api
from config import *
from log import *

import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from typing import *

import utils

# loading token
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

bot = commands.Bot(command_prefix=PREFIX, intents=discord.Intents.default(), help_command=None)
mg = api.Manager(USERS_FILE)

# connection events

@bot.event
async def on_ready():
    log(f'Ready as {bot.user.name}!')

    # commands = await bot.tree.sync()
    # log(f'Synced tree with {len(commands)} commands', level=SUCCESS)


# events

async def handle_modal(inter:discord.Interaction):
    '''
    Handles modal submitting.
    '''
    log(f'{inter.user.id} submitted modal {inter.id}')

    action = inter.data['custom_id'][0]
    id = int(inter.data['custom_id'][1:])

    # note
    if action == 'n':
        note = inter.data['components'][0]['components'][0]['value']
        log(f'{inter.user.id} updated note of {id} to {note}')

        mg.set_note(inter.user.id, id, note)

        embed = discord.Embed(
            color=discord.Color.green(),
            description=f'**Note updated!**\n\n{note}'
        )

    # unknown
    else:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Unknown action!**'
        )

    await inter.response.send_message(embed=embed, ephemeral=True)



@bot.event
async def on_interaction(inter:discord.Interaction):
    '''
    Gets called when a button is pressed or a command is used.
    '''
    if inter.type == discord.InteractionType.modal_submit:
        await handle_modal(inter)
        return
    
    if inter.type != discord.InteractionType.component:
        return
    
    # answering
    log(f'{inter.user.id} pressed on {inter.id}')

    action = inter.data['custom_id'][0]
    id = int(inter.data['custom_id'][1:])

    # removing bookmark
    if action == 'r':
        out = mg.remove_bookmark(inter.user.id, id)

        if not out:
            embed = discord.Embed(
                color=discord.Color.red(),
                description='**Not bookmarked!**'
            )

        else:
            embed = discord.Embed(
                color=discord.Color.green(),
                description='**Bookmark removed!**'
            )

    # setting note
    elif action == 'n':
        bm = mg.get_bookmark(inter.user.id, id)

        if bm != None:
            modal = discord.ui.Modal(
                title='Set a note',
                custom_id=f'n{id}'
            )
            input = discord.ui.TextInput(
                label='Note',
                custom_id='note',
                placeholder=bm.note,
                max_length=50,
                min_length=1
            )
            modal.add_item(input)

            await inter.response.send_modal(modal)
            return
        
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Not bookmarked!**'
        )

    # unknown action
    else:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Unknown action!**'
        )

    await inter.response.send_message(embed=embed, ephemeral=True)

# context menus

@bot.tree.context_menu(name='Set note')
@discord.app_commands.user_install()
async def note(
    inter:discord.Interaction,
    message:discord.Message
):
    '''
    Bookmarks a message.
    '''
    # bookmarking
    out = mg.get_bookmark(inter.user.id, message.id)

    if not out:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Not bookmarked!**'
        )

    else:
        modal = discord.ui.Modal(
            title='Set a note',
            custom_id=f'n{message.id}'
        )
        input = discord.ui.TextInput(
            label='Note',
            custom_id='note',
            placeholder=out.note,
            max_length=50,
            min_length=1
        )
        modal.add_item(input)

        await inter.response.send_modal(modal)
        return
        
    await inter.response.send_message(
        embed=embed, ephemeral=True
    )


@bot.tree.context_menu(name='Bookmark')
@discord.app_commands.user_install()
async def bookmark(
    inter:discord.Interaction,
    message:discord.Message
):
    '''
    Bookmarks a message.
    '''
    # bookmarking
    out = mg.bookmark(inter.user.id, message)

    if not out:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Already bookmarked!**'
        )

        view = discord.ui.View()
        button = discord.ui.Button(
            style=discord.ButtonStyle.red,
            label='Remove bookmark',
            custom_id=f'r{message.id}'
        )
        view.add_item(button)

    else:
        embed = discord.Embed(
            color=discord.Color.green(),
            description='**Bookmarked!**'
        )

        view = discord.ui.View()
        button = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label='Add note',
            custom_id=f'n{message.id}'
        )
        view.add_item(button)
        
    await inter.response.send_message(
        embed=embed, view=view, ephemeral=True
    )


# commands

@bot.tree.command(
    name='search',
    description='Search or view bookmarks.'
)
@discord.app_commands.user_install()
@discord.app_commands.describe(
    prompt='Search prompt. Leave blank to show all.'
)
async def view_text(
    inter:discord.Interaction,
    prompt:str='',
    case:Literal['Case sensitive','Case insensitive']='Case sensitive'
):
    '''
    Searches for bookmarked messages.
    '''
    user = mg.get_user(inter.user.id)
    search: List[api.Message] = user.search(
        prompt, case == 'Case sensitive'
    )

    if len(search) == 0:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**No bookmarks found!**'
        )
    else:
        desc = ''
        
        for i in search:
            desc += f'{i.note}\n'
            desc += f'-# [Jump]({i.link}) ・ {i.id}'
            if i.tags:
                desc += f' ・ Tags: `{"`, `".join(i.tags)}`'

            desc += '\n\n'

        embed = discord.Embed(
            color=discord.Color.green(),
            description=f"**Found {len(search)} bookmarks**\n\n"+desc
        )

    await inter.response.send_message(embed=embed,ephemeral=True)


@bot.tree.command(
    name='manage',
    description='Edit or delete a bookmark.'
)
@discord.app_commands.user_install()
@discord.app_commands.describe(
    id='Bookmark ID'
)
async def view_text(
    inter:discord.Interaction,
    id:str
):
    '''
    Manage a bookmark.
    '''
    if id.isnumeric():
        bm = mg.get_bookmark(inter.user.id, int(id))
    else:
        bm = None

    if bm == None:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Bookmark not found!**'
        )
        await inter.response.send_message(embed=embed,ephemeral=True)
        return
    
    view = discord.ui.View()
    
    button = discord.ui.Button(
        style=discord.ButtonStyle.gray,
        label='Go to message', url=bm.link
    )
    view.add_item(button)

    n_button = discord.ui.Button(
        style=discord.ButtonStyle.blurple,
        label='Set note',
        custom_id=f'n{id}'
    )
    view.add_item(n_button)
    
    r_button = discord.ui.Button(
        style=discord.ButtonStyle.red,
        label='Remove',
        custom_id=f'r{id}'
    )
    view.add_item(r_button)


    embed = discord.Embed(
        color=discord.Color.green(),
        description=f"**Bookmark {id}**"
    )
    embed.add_field(
        name=bm.note,
        value=utils.shorten_string(bm.text, 1024)
    )

    await inter.response.send_message(
        embed=embed, view=view, ephemeral=True
    )
        


## RUNNING BOT
bot.run(TOKEN)