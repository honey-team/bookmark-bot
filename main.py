import time
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

# functions

def get_paginated_embed(
    page:int, results:List[api.Message]
) -> Tuple[discord.Embed, List[api.Message], int]:
    '''
    Converts a list of search results to a paginated embed.
    '''
    max_page = int(len(results)/PAGE_LEN) + \
        (1 if len(results)%PAGE_LEN != 0 else 0)
    page = min(max(page, 1), max_page)
    stripped: List[api.Message] = results[(page-1)*PAGE_LEN:page*PAGE_LEN]

    embed = discord.Embed(
        color=discord.Color.green(),
        title=f"**Found {len(results)} bookmarks**"
    )
    
    for i in stripped:
        desc = f'-# {utils.remove_md(i.author_name)} ・ [Jump]({i.link})'

        if i.attachments:
            lenat = len(i.attachments)
            desc += f' ・ {lenat} {ATT}'

        if i.tags:
            desc += f'\n-# Tags: `{"`, `".join(i.tags)}`'
            
        embed.add_field(name=utils.shorten_string(i.note, NOTE_LEN), value=desc, inline=False)
    embed.set_footer(text=f'Showing page {page} of {max_page}')
    return (embed, stripped, page)



def get_manage_view(
    bm:api.Message,
    jump:bool=True,
    note:bool=True,
    remove:bool=True,
    tags:bool=True
):
    view = discord.ui.View()
    
    if jump:
        button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label='Go to message', url=bm.link
        )
        view.add_item(button)

    if note:
        n_button = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label='Set note',
            custom_id=f's{bm.id}'
        )
        view.add_item(n_button)
    
    if remove:
        r_button = discord.ui.Button(
            style=discord.ButtonStyle.red,
            label='Remove',
            custom_id=f'r{bm.id}'
        )
        view.add_item(r_button)

    if tags:
        t_button = discord.ui.Button(
            style=discord.ButtonStyle.green,
            label='Add tag',
            custom_id=f't{bm.id}',
            row=1,
            disabled=len(bm.tags) >= MAX_TAGS
        )
        view.add_item(t_button)

        if bm.tags != []:
            t_dropdown = discord.ui.Select(
                placeholder='Remove tags...',
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(label=i, value=i) for i in bm.tags
                ],
                custom_id=f'u{bm.id}'
            )
            view.add_item(t_dropdown)

    return view


def get_bm_embed(bm:api.Message):
    '''
    Returns an embed to show when managing a bookmark.
    '''
    # author, send and save time
    send_time = f'<t:{int(bm.sent_at)}:R>'
    save_time = f'<t:{int(bm.saved_at)}:R>'

    stats = f'-# {utils.remove_md(bm.author_name)}'\
        f' ・ {SENT} {send_time} ・ {SAVE} {save_time}'
    
    # tags
    if bm.tags != []:
        stats += f'\n-# Tags: `{"`, `".join(bm.tags)}`'

    # attachments
    lenat = len(bm.attachments)
    if lenat != 0:
        stats += f'\n\n-# {lenat} attachment{"s" if lenat != 1 else ""}'

        for i in bm.attachments:
            stats += f'\n- -# [{i.filename.removesuffix("."+i.extension)}]({i.url}) ・ '\
                f'{i.type.capitalize()}, .{i.extension}'

    # composing embed
    embed = discord.Embed(
        title=bm.note,
        color=discord.Color.green(),
        description=bm.text
    )
    embed.add_field(
        name='',
        value=stats
    )
    # channel and guild id
    embed.set_footer(
        text=f'Message: {bm.id}'+\
            f'\nChannel: {bm.channel_id}'+\
            (f'\nGuild: {bm.guild_id}' if bm.guild_id else '')
    )
    return embed

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
    action = inter.data['custom_id'][0]
    id = int(inter.data['custom_id'][1:])

    # note
    if action == 'n':
        note = inter.data['components'][0]['components'][0]['value']

        mg.set_note(inter.user.id, id, note)

        embed = discord.Embed(
            color=discord.Color.green(),
            description=f'**Note updated!**\n\n{note}'
        )

    # note but editing manage message
    elif action == 's':
        note = inter.data['components'][0]['components'][0]['value']

        mg.set_note(inter.user.id, id, note)

        bm = mg.get_bookmark(inter.user.id, id)
        embed = get_bm_embed(bm)
        view = get_manage_view(bm)

        await inter.response.defer()
        await inter.edit_original_response(
            embed=embed, view=view
        )
        return

    # tag
    elif action == 't':
        tag = inter.data['components'][0]['components'][0]['value']

        out = mg.add_tag(inter.user.id, id, tag)
        tag = tag.lower().replace(' ','_')

        if not out:
            embed = discord.Embed(
                color=discord.Color.red(),
                description=f'**Unable to add a tag!**\n\n'\
                    '- This tag may already be on a message\n'\
                    f'- The maximum number of tags has been reached ({MAX_TAGS})\n'\
                    '- This message is not bookmarked'
            )

        else:
            bm = mg.get_bookmark(inter.user.id, id)
            view = get_manage_view(bm)
            embed = get_bm_embed(bm)

            await inter.response.defer()
            await inter.edit_original_response(
                embed=embed, view=view
            )
            return

    # unknown
    else:
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Unknown action!**'
        )

    await inter.response.send_message(embed=embed, ephemeral=True)


async def handle_dropdown(inter:discord.Interaction):
    '''
    Handles dropdown submitting.

    Only handles dropdowns that do not have a single character in their custom id. 
    '''
    action = inter.data['custom_id'][0]
    id = int(inter.data['custom_id'][1:])
    value = inter.data['values'][0]

    # removing tag
    if action == 'u':
        out = mg.remove_tag(inter.user.id, id, value)

        if not out:
            embed = discord.Embed(
                color=discord.Color.red(),
                description=f'**Tag `{value}` not found or message is not bookmarked!**'
            )

        else:
            # changing message
            bm = mg.get_bookmark(inter.user.id, id)
            view = get_manage_view(bm)
            embed = get_bm_embed(bm)

            await inter.response.defer()
            await inter.edit_original_response(
                embed=embed, view=view
            )
            return

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
    if inter.data['component_type'] == 3:
        if len(inter.data['custom_id']) > 1:
            await handle_dropdown(inter)
            return
        
        action = inter.data['custom_id'][0]
        id = int(inter.data['values'][0])
        
    else:
        action = inter.data['custom_id'][0]
        id = int(inter.data['custom_id'][1:])

    # viewing
    if action == 'b':
        out = mg.get_bookmark(inter.user.id, id)

        if not out:
            embed = discord.Embed(
                color=discord.Color.red(),
                description='**Not bookmarked!**'
            )

        else:
            view = get_manage_view(out)
            embed = get_bm_embed(out)

            await inter.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            return


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

            await inter.response.defer()
            await inter.edit_original_response(embed=embed, view=None)
            return

    # setting note
    elif action == 'n' or action == 's':
        bm = mg.get_bookmark(inter.user.id, id)

        if bm != None:
            modal = discord.ui.Modal(
                title='Set a note',
                custom_id=f'{action}{id}'
            )
            input = discord.ui.TextInput(
                label='Note',
                custom_id='note',
                placeholder=bm.note,
                max_length=NOTE_LEN,
                min_length=1
            )
            modal.add_item(input)

            await inter.response.send_modal(modal)
            return
        
        embed = discord.Embed(
            color=discord.Color.red(),
            description='**Not bookmarked!**'
        )

    # adding tag
    elif action == 't':
        bm = mg.get_bookmark(inter.user.id, id)

        if len(bm.tags) >= MAX_TAGS:
            embed = discord.Embed(
                color=discord.Color.red(),
                description=f'**You can only have {len(bm.tags)} tags on a bookmark!**'
            )
            await inter.response.send_message(embed=embed, ephemeral=True)

        if bm != None:
            modal = discord.ui.Modal(
                title='Add a tag',
                custom_id=f't{id}'
            )
            input = discord.ui.TextInput(
                label='Booru tag',
                custom_id='tag',
                placeholder=bm.note,
                max_length=TAG_LEN,
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
            max_length=NOTE_LEN,
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

    else:
        embed = discord.Embed(
            color=discord.Color.green(),
            description='**Bookmarked!**'
        )

    view = discord.ui.View()
    button = discord.ui.Button(
        style=discord.ButtonStyle.blurple,
        label='Manage',
        custom_id=f'b{message.id}'
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
    prompt='Search prompt. Leave blank to show all.',
    case='Whether the search query is case-sensitive or not.',
    page='Page to skip to.'
)
async def view_text(
    inter:discord.Interaction,
    prompt:str='',
    case:Literal['Case sensitive','Case insensitive']='Case insensitive',
    page:int=1
):
    '''
    Searches for bookmarked messages.
    '''
    if len(prompt) > MAX_PROMPT_LEN:
        embed = discord.Embed(
            color=discord.Color.red(),
            description=f'**Prompt too long!**\n\n'\
                f'{MAX_PROMPT_LEN} characters max.'
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return
    
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
        embed, elements, page = get_paginated_embed(
            page=page, results=search
        )
        elements: List[api.Message]
        max_page = int(len(search)/PAGE_LEN) + \
            (1 if len(search)%PAGE_LEN != 0 else 0)
        
        # view = get_paginated_view(page, max_page)
        view = discord.ui.View()
        
        dd = discord.ui.Select(
            placeholder='Manage...',
            min_values=1,
            max_values=1,
            custom_id='b',
            options=[
                discord.SelectOption(
                    label=i.note,
                    description=f'{i.author_name} - {i.id}',
                    value=f'{i.id}',
                ) for i in elements
            ]
        )
        view.add_item(dd)
        await inter.response.send_message(
            embed=embed, view=view, ephemeral=True
        )
        return

    await inter.response.send_message(embed=embed, ephemeral=True)


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
    
    view = get_manage_view(bm)
    embed = get_bm_embed(bm)

    await inter.response.send_message(
        embed=embed, view=view, ephemeral=True
    )


@view_text.autocomplete('id')
async def manage_autocomplete(
    inter:discord.Interaction,
    current:str
) -> List[discord.app_commands.Choice[str]]:
    '''
    Autocomplete for manage command.
    '''
    user = mg.get_user(inter.user.id)
    
    return [
        discord.app_commands.Choice(
            name=f'{utils.shorten_string(i.note,50)} ({i.id})', value=str(i.id)
        ) for i in user.saved.values()\
        if str(i.id).startswith(current) or current == ''
    ][::-1][:25]

        


## RUNNING BOT
bot.run(TOKEN)