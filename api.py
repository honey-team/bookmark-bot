import time
from typing import *

import discord
from config import *
import json
import os
from log import *
import utils


# handling args

def handle_arg(arg: str, value: str, messages:"List[Message]", case:bool) -> List[int]:
    '''
    Searches the given list of messages following the given rule.

    Returns a list of message IDs.
    '''
    arg = arg.lower()

    # value
    value = value if case else value.lower()
    out = ''
    for index, i in enumerate(value):
        if index < len(value)-1:
            next = value[index+1]
        else:
            next = None

        if index > 0:
            prev = value[index-1]
        else:
            prev = None

        if i == '\\' and next == '_':
            continue
        elif i == '_' and prev != '\\':
            out += ' '
        else:
            out += i

    value = out

    # keyword
    if arg in ['keyword', 'kw']:
        return [
            m.id for m in messages if value in (
                m.text if case else m.text.lower()
            ) or value in (
                m.note if case else m.note.lower()
            )
        ]
    
    # text
    if arg == 'text':
        return [
            m.id for m in messages if value in (
                m.text if case else m.text.lower()
            )
        ]

    # note
    if arg == 'note':
        return [
            m.id for m in messages if value in (
                m.note if case else m.note.lower()
            )
        ]
    
    # guild id
    if arg in ['server','guild']:
        ids = value.lower().split(' ')

        return [
            m.id for m in messages if str(m.guild_id).lower() in ids
        ]
    
    # channel id
    if arg in ['channel']:
        ids = value.split(' ')

        return [
            m.id for m in messages if str(m.channel_id) in ids
        ]
    
    # attachment amount
    if arg == 'attachments':
        type = '='

        if value.startswith('>='):
            value = value[2:]
            type = '>='
        elif value.startswith('<='):
            value = value[2:]
            type = '<='

        elif value.startswith('>'):
            value = value[1:]
            type = '>'
        elif value.startswith('<'):
            value = value[1:]
            type = '<'
        
        if not value.isnumeric():
            return []
        
        value = int(value)
        if value < 0:
            return []

        out = []

        # im sorry
        for i in messages:
            if type == '=' and len(i.attachments) == value\
            or type == '<' and len(i.attachments) < value\
            or type == '>' and len(i.attachments) > value\
            or type == '<=' and len(i.attachments) <= value\
            or type == '>=' and len(i.attachments) >= value:
                out.append(i.id)

        return out
    
    # nope
    return []


 
# user and user-related classes

class User:
    def __init__(self, id:int, data:dict={}):
        '''
        Represents a user.
        '''
        self.id: int = id
        self.saved: Dict[int, Message] = {
            int(k): Message(int(k), v) for k,v in data.get('saved', {}).items()
        }

    
    def to_dict(self) -> dict:
        '''
        Converts the class to a dictionary to store in the file.
        '''
        return {
            "saved": {k: v.to_dict() for k,v in self.saved.items()}
        }
    

    def search(self, prompt:str, case_sensitive:bool) -> "List[Message]":
        '''
        Searches the user's saved messages for the given prompt.
        '''
        if prompt == '': return [i for i in self.saved.values()]

        codes = prompt.split(' ')
        results: List[List[int]] = []
        merged: Set[int] = set()

        kw: List[str] = []
        current_kw: str = ''
        arg = None

        for i in codes:
            if arg != None:
                ids = handle_arg(arg, i, self.saved.values(), case_sensitive)
                results.append(ids)

                for j in ids:
                    merged.add(j)

                arg = None

            elif i[0] != '-':
                i = i.removeprefix('\\')
                current_kw += i+' '
                continue

            else:
                if current_kw != '':
                    kw.append(current_kw[:-1])

                current_kw = ''
                arg = i[1:]

        if current_kw != '':
            kw.append(current_kw[:-1])

        # keywords
        for i in kw:
            ids = handle_arg('kw', i, self.saved.values(), case_sensitive)
            results.append(ids)

            for j in ids:
                merged.add(j)

        # and-ing
        merged = list(merged)
        out = []

        for i in merged:
            for l in results:
                if i not in l:
                    break
            else:
                out.append(i)

        # getting messages
        out = [self.saved[i] for i in out]

        return out


# message and message-related classes

class Attachment:
    def __init__(self, id:int, data:dict):
        '''
        Represents a message attachment.
        '''
        self.parent: int = id
        self.id: int = data['id']
        self.type: str = data.get('type', 'none')
        self.extension: str = data.get('extension', 'none')
        self.filename: str = data['filename']
        self.url: str = data['url']

    
    def to_dict(self) -> dict:
        '''
        Converts the class to a dictionary to store in the file.
        '''
        return {
            "id": self.id,
            "type": self.type,
            "extension": self.extension,
            "filename": self.filename,
            "url": self.url
        }
    

class Message:
    def __init__(self, id:int, data:dict):
        '''
        Represents a saved message.
        '''
        self.id: int = id
        self.link: str = data['link']
        self.guild_id: "int | None" = data.get('guild_id', None)
        self.channel_id: int = data['channel_id']
        self.text: str = data.get('text', '')
        self.note: str = data.get(
            'note', utils.remove_md(utils.shorten_string(self.text), True)
        )
        if len(self.note) == 0:
            self.note = '...'
        self.saved_at: float = data.get('saved_at', time.time())
        self.tags: List[str] = data.get('tags', [])
        self.attachments: List[Attachment] = [
            Attachment(self.id, i) for i in data.get('attachments', [])
        ]

    
    def to_dict(self) -> dict:
        '''
        Converts the class to a dictionary to store in the file.
        '''
        return {
            "link": self.link,
            "text": self.text,
            "note": self.note,
            "saved_at": self.saved_at,
            "tags": self.tags,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "attachments": [i.to_dict() for i in self.attachments]
        }


# manager

class Manager:
    def __init__(self, users_file:str):
        '''
        API and backend manager.
        '''
        self.users_file: str = users_file

        self.reload()


    def new(self):
        '''
        Rewrites the old database with the new one.
        '''
        self.users: Dict[int, User] = {}

        self.commit()


    def panic(self):
        '''
        Creates a duplicate of the database and creates a new one.
        '''
        log('Panic!', 'api', WARNING)

        # copying file
        if os.path.exists(self.users_file):
            os.rename(self.users_file, self.users_file+'.bak')
            log(f'Cloned user data file to {self.users_file}.bak', 'api')

        # creating a new one
        self.new()


    def reload(self):
        '''
        Reloads user data and bot data.
        '''
        # user data
        try:
            with open(self.users_file, encoding='utf-8') as f:
                data = json.load(f)
        except:
            self.panic()
            return

        self.users = {int(id): User(int(id), data) for id, data in data['users'].items()}

        # saving
        self.commit()


    def commit(self):
        '''
        Saves user data to the file.
        '''
        data = {
            'users': {}
        }

        # users
        for i in self.users:
            data['users'][i] = self.users[i].to_dict()

        # saving
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)


    def check_user(self, id:int):
        '''
        Checks if user exists in database. If not, creates one.
        '''
        if id in self.users:
            return
        
        self.users[id] = User(id)


    def get_user(self, id:int) -> User:
        '''
        Returns user by ID.

        Automatically checks the user.
        '''
        self.check_user(id)
        return self.users[id]


    def get_bookmark(self, user:int, message:int) -> "Message | None":
        '''
        Returns a bookmarked message by ID.
        '''
        guser = self.get_user(user)

        if message not in guser.saved:
            return None

        return guser.saved[message]


    def bookmark(self, user:int, message:discord.Message) -> bool:
        '''
        Bookmarks a message.

        Returns whether the message is successfully bookmarked.
        '''
        guser = self.get_user(user)
        
        if message.id in guser.saved:
            return False

        guser.saved[message.id] = Message(message.id, {
            "link": message.jump_url,
            "text": message.content,
            "guild_id": message.guild.id if message.guild else None,
            "channel_id": message.channel.id
        })
        self.commit()
        return True


    def set_note(self, user:int, message:int, note:str) -> bool:
        '''
        Sets a note for a bookmarked message.

        Returns whether the note was successfully updated.
        '''
        guser = self.get_user(user)
        
        if message not in guser.saved:
            return False

        guser.saved[message].note = utils.remove_md(note, True)
        self.commit()
        return True


    def remove_bookmark(self, user:int, message:int) -> bool:
        '''
        Unbookmarks a message.

        Returns whether the message is successfully unbookmarked.
        '''
        guser = self.get_user(user)
        
        if message not in guser.saved:
            return False

        guser.saved.pop(message)
        self.commit()
        return True
