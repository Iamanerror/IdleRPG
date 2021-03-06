"""
Original, main Paginator class written by EvieePy
Modified by the IdleRPG Project

The IdleRPG Discord Bot
Copyright (C) 2018-2019 Diniboy and Gelbpunkt

This software is dual-licensed under the GNU Affero General Public License for non-commercial and the Travitia License for commercial use.
For more information, see README.md and LICENSE.md.

The MIT License (MIT)
Copyright (c) 2018 EvieePy
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""


import asyncio
import discord
from config import primary_colour


async def pager(entries, chunk: int):
    for x in range(0, len(entries), chunk):
        yield entries[x : x + chunk]


class NoChoice(discord.ext.commands.CommandInvokeError):
    pass


class Paginator:

    __slots__ = (
        "entries",
        "extras",
        "title",
        "description",
        "colour",
        "footer",
        "length",
        "prepend",
        "append",
        "fmt",
        "timeout",
        "ordered",
        "controls",
        "controller",
        "pages",
        "current",
        "previous",
        "eof",
        "base",
        "names",
    )

    def __init__(self, **kwargs):
        self.entries = kwargs.get("entries", None)
        self.extras = kwargs.get("extras", None)

        self.title = kwargs.get("title", None)
        self.description = kwargs.get("description", None)
        self.colour = kwargs.get("colour", primary_colour)
        self.footer = kwargs.get("footer", None)

        self.length = kwargs.get("length", 10)
        self.prepend = kwargs.get("prepend", "")
        self.append = kwargs.get("append", "")
        self.fmt = kwargs.get("fmt", "")
        self.timeout = kwargs.get("timeout", 90)
        self.ordered = kwargs.get("ordered", False)

        self.controller = None
        self.pages = []
        self.names = []
        self.base = None

        self.current = 0
        self.previous = 0
        self.eof = 0

        self.controls = {"⏮": 0.0, "◀": -1, "⏹": "stop", "▶": +1, "⏭": None}

    async def indexer(self, ctx, ctrl):
        if ctrl == "stop":
            ctx.bot.loop.create_task(self.stop_controller(self.base))

        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)

    async def reaction_controller(self, ctx):
        bot = ctx.bot
        author = ctx.author

        self.base = await ctx.send(embed=self.pages[0])

        if len(self.pages) == 1:
            await self.base.add_reaction("⏹")
        else:
            for reaction in self.controls:
                try:
                    await self.base.add_reaction(reaction)
                except discord.HTTPException:
                    return

        def check(r, u):
            if str(r) not in self.controls.keys():
                return False
            elif u.id == bot.user.id or r.message.id != self.base.id:
                return False
            elif u.id != author.id:
                return False
            return True

        while True:
            try:
                react, user = await bot.wait_for(
                    "reaction_add", check=check, timeout=self.timeout
                )
            except asyncio.TimeoutError:
                return ctx.bot.loop.create_task(self.stop_controller(self.base))

            control = self.controls.get(str(react))

            try:
                await self.base.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            self.previous = self.current
            await self.indexer(ctx, control)

            if self.previous == self.current:
                continue

            try:
                await self.base.edit(embed=self.pages[self.current])
            except KeyError:
                pass

    async def stop_controller(self, message):
        try:
            await message.delete()
        except discord.HTTPException:
            pass

        try:
            self.controller.cancel()
        except Exception:
            pass

    def formmater(self, chunk):
        return "\n".join(
            f"{self.prepend}{self.fmt}{value}{self.fmt[::-1]}{self.append}"
            for value in chunk
        )

    async def paginate(self, ctx):
        if self.extras:
            self.pages = [p for p in self.extras if isinstance(p, discord.Embed)]

        if self.entries:
            chunks = [c async for c in pager(self.entries, self.length)]

            for index, chunk in enumerate(chunks):
                page = discord.Embed(
                    title=f"{self.title} - {index + 1}/{len(chunks)}", color=self.colour
                )
                page.description = self.formmater(chunk)

                if hasattr(self, "footer"):
                    if self.footer:
                        page.set_footer(text=self.footer)
                self.pages.append(page)

        if not self.pages:
            raise ValueError(
                "There must be enough data to create at least 1 page for pagination."
            )

        self.eof = float(len(self.pages) - 1)
        self.controls["⏭"] = self.eof
        self.controller = ctx.bot.loop.create_task(self.reaction_controller(ctx))


class ChoosePaginator(Paginator):

    __slots__ = (
        "entries",
        "extras",
        "title",
        "description",
        "colour",
        "footer",
        "length",
        "prepend",
        "append",
        "fmt",
        "timeout",
        "ordered",
        "controls",
        "controller",
        "pages",
        "current",
        "previous",
        "eof",
        "base",
        "names",
        "choices",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controls = {
            "⏮": 0.0,
            "◀": -1,
            "⏹": "stop",
            "▶": +1,
            "⏭": None,
            "\U0001f535": "choose",
        }
        self.choices = kwargs.get("choices")
        items = self.entries or self.extras
        assert len(items) == len(self.choices)

    async def indexer(self, ctx, ctrl):
        if ctrl == "stop":
            await self.stop_controller(self.base)
            raise NoChoice("You didn't choose anything.")

        elif isinstance(ctrl, int):
            self.current += ctrl
            if self.current > self.eof or self.current < 0:
                self.current -= ctrl
        else:
            self.current = int(ctrl)

    async def reaction_controller(self, ctx):
        bot = ctx.bot
        author = ctx.author

        self.base = await ctx.send(embed=self.pages[0])

        if len(self.pages) == 1:
            await self.base.add_reaction("⏹")
        else:
            for reaction in self.controls:
                try:
                    await self.base.add_reaction(reaction)
                except discord.HTTPException:
                    return

        def check(r, u):
            if str(r) not in self.controls.keys():
                return False
            elif u.id == bot.user.id or r.message.id != self.base.id:
                return False
            elif u.id != author.id:
                return False
            return True

        while True:
            try:
                react, user = await bot.wait_for(
                    "reaction_add", check=check, timeout=self.timeout
                )
            except asyncio.TimeoutError:
                # return ctx.bot.loop.create_task(self.stop_controller(self.base))
                await self.stop_controller(self.base)
                raise NoChoice("You didn't choose anything.")

            control = self.controls.get(str(react))

            try:
                await self.base.remove_reaction(react, user)
            except discord.HTTPException:
                pass

            if control == "choose":
                await self.stop_controller(self.base)
                return self.choices[self.current]

            self.previous = self.current
            await self.indexer(ctx, control)

            if self.previous == self.current:
                continue

            try:
                await self.base.edit(embed=self.pages[self.current])
            except KeyError:
                pass

    async def paginate(self, ctx):
        if self.extras:
            self.pages = [p for p in self.extras if isinstance(p, discord.Embed)]

        if self.entries:
            chunks = [c async for c in pager(self.entries, self.length)]

            for index, chunk in enumerate(chunks):
                page = discord.Embed(
                    title=f"{self.title} - {index + 1}/{len(chunks)}", color=self.colour
                )
                page.description = self.formmater(chunk)

                if self.footer:
                    page.set_footer(text=self.footer)
                self.pages.append(page)

        if not self.pages:
            raise ValueError(
                "There must be enough data to create at least 1 page for pagination."
            )

        self.eof = float(len(self.pages) - 1)
        self.controls["⏭"] = self.eof
        # self.controller = ctx.bot.loop.create_task(asyncio.gather(self.reaction_controller(ctx))
        return await self.reaction_controller(ctx)


class Choose:
    def __init__(
        self,
        entries,
        title=None,
        footer=None,
        colour=None,
        timeout=30,
        return_index=False,
    ):
        self.entries = entries
        self.title = title or "Untitled"
        self.footer = footer
        self.colour = colour or primary_colour
        self.timeout = timeout
        self.return_index = return_index

    async def paginate(self, ctx, location=None):
        if len(self.entries) > 10:
            raise ValueError("Exceeds maximum size")
        elif len(self.entries) < 2:
            raise ValueError(
                "There must be enough data to create at least 1 page for choosing."
            )
        em = discord.Embed(title=self.title, description="", colour=self.colour)
        self.emojis = []
        for index, chunk in enumerate(self.entries):
            if index < 9:
                self.emojis.append(f"{index+1}\u20e3")
            else:
                self.emojis.append("\U0001f51f")
            em.description = f"{em.description}{self.emojis[index]} {chunk}\n"

        if self.footer:
            em.set_footer(text=self.footer)

        self.controller = em
        return await self.reaction_controller(ctx, location=location)

    async def reaction_controller(self, ctx, location):
        if not location:
            base = await ctx.send(embed=self.controller)
        else:
            base = await location.send(embed=self.controller)

        for emoji in self.emojis:
            await base.add_reaction(emoji)

        def check(r, u):
            if str(r) not in self.emojis:
                return False
            elif u.id == ctx.bot.user.id or r.message.id != base.id:
                return False
            if not location:
                if u.id != ctx.author.id:
                    return False
            else:
                if u.id != location.id:
                    return False
            return True

        try:
            react, user = await ctx.bot.wait_for(
                "reaction_add", check=check, timeout=self.timeout
            )
        except asyncio.TimeoutError:
            await self.stop_controller(base)
            raise NoChoice("You didn't choose anything.")

        control = self.entries[self.emojis.index(str(react))]

        await self.stop_controller(base)
        if not self.return_index:
            return control
        else:
            return self.emojis.index(str(react))

    async def stop_controller(self, message):
        try:
            await message.delete()
        except discord.HTTPException:
            pass


class Akinator:
    def __init__(
        self,
        entries,
        title=None,
        footer_text=None,
        footer_icon=None,
        colour=None,
        timeout=30,
        return_index=False,
        undo=True,
        view_current=True,
        msg=None,
        delete=True,
    ):
        self.entries = entries
        self.title = title or "Untitled"
        self.footer_text = footer_text or discord.Embed.Empty
        self.footer_icon = footer_icon or discord.Embed.Empty
        self.colour = colour or primary_colour
        self.timeout = timeout
        self.return_index = return_index
        self.undo = undo
        self.view_current = view_current
        self.msg = msg
        self.delete = delete

    async def paginate(self, ctx):
        if len(self.entries) > 10:
            raise ValueError("Exceeds maximum size")
        elif len(self.entries) < 2:
            raise ValueError(
                "There must be enough data to create at least 1 page for choosing."
            )
        em = discord.Embed(title=self.title, description="", colour=self.colour)
        self.emojis = []
        for index, chunk in enumerate(self.entries):
            if index < 9:
                self.emojis.append(f"{index+1}\u20e3")
            else:
                self.emojis.append("\U0001f51f")
            em.description = f"{em.description}{self.emojis[index]} {chunk}\n"

        em.set_footer(icon_url=self.footer_icon, text=self.footer_text)

        self.controller = em
        return await self.reaction_controller(ctx)

    async def reaction_placer(self, base):
        for emoji in self.emojis:
            await base.add_reaction(emoji)

        if self.undo:
            self.emojis.append("\U000021a9")
            await base.add_reaction("\U000021a9")
        if self.view_current:
            self.emojis.append("\U00002139")
            await base.add_reaction("\U00002139")

    async def reaction_controller(self, ctx):
        if not self.msg:
            base = await ctx.send(embed=self.controller)
        else:
            base = self.msg
            await self.msg.edit(content=None, embed=self.controller)

        place_task = ctx.bot.loop.create_task(self.reaction_placer(base))

        def check(r, u):
            if str(r) not in self.emojis:
                return False
            elif u.id == ctx.bot.user.id or r.message.id != base.id:
                return False
            elif u.id != ctx.author.id:
                return False
            return True

        try:
            react, user = await ctx.bot.wait_for(
                "reaction_add", check=check, timeout=self.timeout
            )
            place_task.cancel()
        except asyncio.TimeoutError:
            place_task.cancel()
            await self.stop_controller(base)
            return "nochoice"

        try:
            control = self.entries[self.emojis.index(str(react))]
        except IndexError:
            await self.stop_controller(base)
            if str(react) == "\U000021a9":
                return "undo"
            elif str(react) == "\U00002139":
                return "current"

        await self.stop_controller(base)
        if not self.return_index:
            return control
        else:
            return self.emojis.index(str(react))

    async def stop_controller(self, message):
        try:
            if self.delete:
                await message.delete()
            else:
                pass
        except discord.HTTPException:
            pass
