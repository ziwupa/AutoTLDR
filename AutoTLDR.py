# -*- coding: utf-8 -*-
# meta developer: @ziwupa
# scope: heroku_only

from .. import loader, utils

try:
    from herokutl.utils import get_display_name
except ImportError:
    from telethon.utils import get_display_name

import aiohttp
import html
import os
import re
import tempfile


@loader.tds
class AutoTLDRMod(loader.Module):
    """AI-анализ сообщений. Реплай = разбор человека. Без реплая = разбор чата. .tldr @user = разбор юзера по нику."""

    strings = {
        "name": "AutoTLDR",
        "no_target": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Ответь на сообщение, укажи @username или просто .tldr для анализа чата.</b>"
        ),
        "no_key": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>API-ключ для провайдера <code>{provider}</code> не задан в конфиге.</b>"
        ),
        "no_msgs": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>У {name} нет текстовых сообщений в этом чате.</b>"
        ),
        "no_msgs_chat": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>В этом чате нет текстовых сообщений.</b>"
        ),
        "user_not_found": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Пользователь <code>{user}</code> не найден.</b>"
        ),
        "collecting": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Собираю сообщения {name}...</b>"
        ),
        "collecting_chat": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Собираю последние сообщения чата...</b>"
        ),
        "analyzing": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Анализирую {count} сообщений {name}...</b>"
        ),
        "analyzing_chat": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Анализирую {count} сообщений чата...</b>"
        ),
        "header_user": (
            "<emoji document_id=5215493672150684239>🧠</emoji> "
            "<b>Разбор <a href=\"tg://user?id={sender_id}\">{name}</a></b>"
            " <i>(по {count} сообщ.)</i>\n\n"
        ),
        "header_chat": (
            "<emoji document_id=5215493672150684239>🧠</emoji> "
            "<b>О чём щас чат</b> <i>(по {count} сообщ.)</i>\n\n"
        ),
        "blocked": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Gemini заблокировал ответ (фильтр безопасности).</b>"
            "<i> Возможно, в сообщениях слишком жёсткий контент.</i>"
        ),
        "error": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Ошибка:</b> <code>{error}</code>"
        ),
        "kl_no_reply": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Ответь .kl на сообщение/файл со списком ключей.</b>"
        ),
        "kl_added": (
            "<emoji document_id=5197688912457245639>✅</emoji> "
            "<b>Gemini:</b> +<code>{g_added}</code> (всего <code>{g_total}</code>)"
            " | дублей: <code>{g_dupes}</code>\n"
            "<b>OpenRouter:</b> +<code>{or_added}</code> (всего <code>{or_total}</code>)"
            " | дублей: <code>{or_dupes}</code>"
        ),
        "kl_no_keys": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>В сообщении не найдено Gemini/OpenRouter ключей.</b>"
        ),
        "kl_cleared": (
            "<emoji document_id=5197688912457245639>✅</emoji> "
            "<b>Файлы ключей очищены.</b>"
        ),
        "cmp_no_targets": (
            "<emoji document_id=5210952531676504517>🚫</emoji> "
            "<b>Укажи двух людей: .tldrcmp @user1 @user2 [кол-во]</b>\n"
            "<i>Или ответь на сообщение первого + .tldrcmp @user2</i>"
        ),
        "cmp_collecting": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Собираю {name1} ({c1}...) и {name2} ({c2}...)...</b>"
        ),
        "cmp_analyzing": (
            "<emoji document_id=5451732530048802485>⏳</emoji> "
            "<b>Сравниваю {name1} ({c1} сообщ.) и {name2} ({c2} сообщ.)...</b>"
        ),
        "cmp_header": (
            "<emoji document_id=5215493672150684239>🧠</emoji> "
            "<b><a href=\"tg://user?id={sid1}\">{name1}</a>"
            " vs "
            "<a href=\"tg://user?id={sid2}\">{name2}</a></b>"
            " <i>(по {c1} и {c2} сообщ.)</i>\n\n"
        ),
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "provider",
                "gemini",
                doc="Провайдер AI: gemini / openrouter / openai",
                validator=loader.validators.Choice(["gemini", "openrouter", "openai"]),
            ),
            loader.ConfigValue(
                "gemini_api_key",
                "",
                doc="API-ключ Google Gemini",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "openrouter_api_key",
                "",
                doc="API-ключ OpenRouter",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "openai_api_key",
                "",
                doc="API-ключ OpenAI",
                validator=loader.validators.Hidden(),
            ),
            loader.ConfigValue(
                "gemini_model", "gemini-3.1-pro-preview", doc="Модель Gemini"
            ),
            loader.ConfigValue(
                "keys_file",
                "gemini_keys.txt",
                doc=(
                    "Файл с пулом Gemini-ключей (по одному на строку). "
                    "Если есть — ключи берутся из него по очереди. "
                    "Нет файла — используется gemini_api_key. "
                    "В сам модуль ключи НЕ зашиты."
                ),
            ),
            loader.ConfigValue(
                "or_keys_file",
                "openrouter_keys.txt",
                doc=(
                    "Файл с пулом OpenRouter-ключей (sk-or-v1-...). "
                    "Если есть — ключи берутся по очереди. "
                    "Нет файла — используется openrouter_api_key."
                ),
            ),
            loader.ConfigValue(
                "openrouter_model",
                "openai/gpt-4o-mini",
                doc="Модель OpenRouter",
            ),
            loader.ConfigValue("openai_model", "gpt-5.5", doc="Модель OpenAI"),
            loader.ConfigValue(
                "default_count",
                100,
                doc="Сколько сообщений анализировать (мин. 1)",
                validator=loader.validators.Integer(minimum=1),
            ),
            loader.ConfigValue(
                "allow_swearing",
                True,
                doc="Разрешить AI материться, если в чате треш",
                validator=loader.validators.Boolean(),
            ),
        )

    async def client_ready(self, client, db):
        self._client = client
        self._key_idx = 0
        self._sender_cache = {}

    # ---------- keys ----------

    def _load_key_pool(self) -> list:
        path = self.config["keys_file"]
        if not path:
            return []
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return []
        keys = re.findall(r"AIza[0-9A-Za-z_-]{15,}", raw)
        seen = set()
        pool = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                pool.append(k)
        return pool

    def _load_or_key_pool(self) -> list:
        """Читает пул OpenRouter-ключей из внешнего файла."""
        path = self.config["or_keys_file"]
        if not path:
            return []
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return []
        keys = re.findall(r"sk-or-v1-[0-9a-fA-F]{30,}", raw)
        seen = set()
        pool = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                pool.append(k)
        return pool

    # ---------- prompts ----------

    def _swear_rule(self) -> str:
        return (
            "Можешь свободно материться и использовать жёсткий, грубый сленг, "
            "особенно если в сообщениях трэш, токсик или дичь — "
            "не сдерживайся, будь живым и резким."
            if self.config["allow_swearing"]
            else "Пиши без мата, нейтрально-разговорно."
        )

    def _format_rules(self) -> str:
        return (
            "ФОРМАТ ОТВЕТА (строго):\n"
            "- Каждый тезис — отдельной строкой.\n"
            "- Каждую строку начинай с короткого жирного заголовка в HTML-теге <b>...</b>, "
            "потом двоеточие и текст. Пример: <b>Темы:</b> мемы, доты, нытьё про работу.\n"
            "- 4-7 строк, не больше.\n"
            "- Все имена/ники людей выделяй жирным: <b>Вася</b>, <b>Петя</b>.\n"
            "- Последняя строка: <b>Итог:</b> краткое резюме в 1 предложение.\n"
            "- Только чистый текст и теги <b></b>. Без markdown, без ```, без emoji-спама.\n\n"
        )

    def _build_user_prompt(self, name: str, username: str, messages: list) -> str:
        transcript = "\n".join(messages)
        handle = f" (@{username})" if username else ""
        return (
            f"Ты анализируешь сообщения пользователя «{name}»{handle} из группового чата. "
            "Сделай короткий, цепкий разбор: о чём он в основном пишет, какое у него "
            "настроение/характер, манера общения, повторяющиеся темы, и что от него вообще "
            "хотят/что он хочет. Будь конкретным, без воды и без вступлений.\n"
            f"{self._swear_rule()}\n\n"
            f"{self._format_rules()}"
            f"СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ:\n{transcript}"
        )

    def _build_chat_prompt(self, messages: list) -> str:
        transcript = "\n".join(messages)
        return (
            "Ты анализируешь последние сообщения из группового чата. "
            "Сделай короткий, цепкий разбор: о чём прямо сейчас идёт разговор, "
            "какие темы обсуждаются, какая атмосфера (дружелюбная / токсичная / "
            "флуд / драма / треш / деловая), кто что говорит и в каком настроении, "
            "есть ли назревающий конфликт или движуха.\n"
            "Упоминай конкретных людей по никам из сообщений, чтобы было понятно "
            "кто есть кто и кто что сделал.\n"
            f"{self._swear_rule()}\n\n"
            f"{self._format_rules()}"
            f"СООБЩЕНИЯ ЧАТА (формат: [ник]: текст):\n{transcript}"
        )

    def _build_cmp_prompt(
        self, name1: str, name2: str,
        msgs1: list, msgs2: list,
    ) -> str:
        t1 = "\n".join(msgs1)
        t2 = "\n".join(msgs2)
        return (
            f"Ты сравниваешь двух участников чата: «{name1}» и «{name2}». "
            "Разбери их по пунктам: общие темы, манера общения, токсичность/агрессия, "
            "кто чаще провоцирует, как относятся друг к другу, кто активнее, "
            "в чём они похожи и в чём различаются.\n"
            f"{self._swear_rule()}\n\n"
            f"{self._format_rules()}"
            f"СООБЩЕНИЯ {name1}:\n{t1}\n\n"
            f"СООБЩЕНИЯ {name2}:\n{t2}"
        )

    # ---------- AI ----------

    @staticmethod
    def _parse_gemini_text(data: dict) -> str:
        candidates = data.get("candidates")
        if not candidates:
            fb = data.get("promptFeedback", {})
            block = fb.get("blockReason", "")
            details = ""
            if block:
                reasons = {
                    "SAFETY": "фильтр безопасности",
                    "BLOCKLIST": "блок-лист",
                    "PROHIBITED_CONTENT": "запрещённый контент",
                    "OTHER": block,
                }
                details = f" (причина: {reasons.get(block, block)})"
            safety = fb.get("safetyRatings", [])
            if safety:
                triggered = [s["category"] for s in safety if s.get("probability") in ("HIGH", "MEDIUM")]
                if triggered:
                    details += f" [сработало: {', '.join(triggered)}]"
            raise RuntimeError(
                f"Gemini: пустой ответ{details}. "
                "Возможно, слишком длинный промпт или запрещённый контент."
            )
        c0 = candidates[0]
        finish = c0.get("finishReason", "STOP")
        if finish and finish != "STOP":
            reasons = {
                "SAFETY": "фильтр безопасности заблокировал ответ",
                "RECITATION": "ответ похож на копипасту (recitation)",
                "MAX_TOKENS": "превышен лимит токенов",
                "BLOCKLIST": "контент попал в блок-лист",
                "PROHIBITED_CONTENT": "запрещённый контент",
                "SPII": "обнаружены персональные данные (SPII)",
                "MALFORMED_FUNCTION_CALL": "некорректный function call",
                "OTHER": f"неизвестная причина: {finish}",
            }
            reason = reasons.get(finish, f"неизвестный finishReason: {finish}")
            raise RuntimeError(f"Gemini заблокировал ответ: {reason}")
        content = c0.get("content")
        if not content:
            raise RuntimeError(
                f"Gemini: пустой content (finishReason={finish}). "
                "Попробуй другую модель или отключи мат."
            )
        parts = content.get("parts")
        if not parts:
            raise RuntimeError("Gemini: пустой ответ (нет parts)")
        return parts[0].get("text", "")

    async def _gemini_call(self, key: str, model: str, payload: dict):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                data = await r.json()
                return r.status, data

    async def _ask_gemini(self, prompt: str) -> str:
        model = self.config["gemini_model"]
        # обрезаем промпт, если слишком длинный
        max_prompt = 90000
        if len(prompt) > max_prompt:
            prompt = prompt[:max_prompt]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {"category": cat, "threshold": "BLOCK_NONE"}
                for cat in (
                    "HARM_CATEGORY_HARASSMENT",
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "HARM_CATEGORY_DANGEROUS_CONTENT",
                )
            ],
        }

        pool = self._load_key_pool()
        if not pool:
            key = self.config["gemini_api_key"]
            if not key:
                raise RuntimeError(
                    self.strings("no_key").format(provider="gemini")
                )
            status, data = await self._gemini_call(key, model, payload)
            if status != 200:
                raise RuntimeError(f"Gemini {status}: {data}")
            return self._parse_gemini_text(data)

        n = len(pool)
        last_err = None
        for offset in range(n):
            idx = (self._key_idx + offset) % n
            key = pool[idx]
            status, data = await self._gemini_call(key, model, payload)
            if status == 200:
                self._key_idx = (idx + 1) % n
                return self._parse_gemini_text(data)
            if status == 429:
                last_err = f"Gemini 429 (ключ #{idx + 1})"
                continue
            raise RuntimeError(f"Gemini {status}: {data}")

        raise RuntimeError(
            f"Все {n} ключей упёрлись в лимит (429). Последнее: {last_err}"
        )

    async def _or_call(self, key: str, model: str, payload: dict, extra_headers: dict):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        headers.update(extra_headers)
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as r:
                data = await r.json()
                return r.status, data

    async def _ask_openai_like(self, prompt: str, openrouter: bool) -> str:
        if openrouter:
            model = self.config["openrouter_model"]
            provider = "openrouter"
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            extra = {
                "HTTP-Referer": "https://github.com/coddrago/Heroku",
                "X-Title": "Heroku Userbot",
            }

            pool = self._load_or_key_pool()
            if not pool:
                key = self.config["openrouter_api_key"]
                if not key:
                    raise RuntimeError(self.strings("no_key").format(provider=provider))
                status, data = await self._or_call(key, model, payload, extra)
                if status != 200:
                    raise RuntimeError(f"{provider} {status}: {data}")
                return data["choices"][0]["message"]["content"]

            n = len(pool)
            last_err = None
            for offset in range(n):
                idx = (self._key_idx + offset) % n
                key = pool[idx]
                status, data = await self._or_call(key, model, payload, extra)
                if status == 200:
                    self._key_idx = (idx + 1) % n
                    return data["choices"][0]["message"]["content"]
                if status == 429:
                    last_err = f"OpenRouter 429 (ключ #{idx + 1})"
                    continue
                raise RuntimeError(f"{provider} {status}: {data}")

            raise RuntimeError(
                f"Все {n} ключей OpenRouter упёрлись в лимит. Последнее: {last_err}"
            )
        else:
            key = self.config["openai_api_key"]
            model = self.config["openai_model"]
            provider = "openai"
            if not key:
                raise RuntimeError(self.strings("no_key").format(provider=provider))
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as r:
                    data = await r.json()
                    if r.status != 200:
                        raise RuntimeError(f"{provider} {r.status}: {data}")
                    return data["choices"][0]["message"]["content"]

    async def _ask_ai(self, prompt: str) -> str:
        provider = self.config["provider"]
        if provider == "gemini":
            return await self._ask_gemini(prompt)
        if provider == "openrouter":
            return await self._ask_openai_like(prompt, openrouter=True)
        return await self._ask_openai_like(prompt, openrouter=False)

    # ---------- formatting ----------

    @staticmethod
    def _sanitize(text: str) -> str:
        text = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "").strip()
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*•]\s*", "", line)
            line = html.escape(line)
            line = line.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
            line = line.replace("&lt;/a&gt;", "</a>")
            line = re.sub(r"&lt;a\s+([^&]+)&gt;", r"<a \1>", line)
            lines.append(line)
        return "<blockquote>" + "\n".join(lines) + "</blockquote>"

    @staticmethod
    def _linkify_names(text: str, senders: dict) -> str:
        if not senders:
            return text
        items = sorted(senders.items(), key=lambda x: -len(x[1]))
        for sid, name in items:
            if not name or len(name) < 2:
                continue
            safe_name = utils.escape_html(name)
            link = f'<a href="tg://user?id={sid}">{safe_name}</a>'
            text = re.sub(
                rf"(?<![a-zA-Zа-яёЁ0-9_</>]){re.escape(safe_name)}(?![a-zA-Zа-яёЁ0-9_</>])",
                link,
                text,
                flags=re.IGNORECASE,
            )
        return text

    # ---------- message media detection ----------

    @staticmethod
    def _format_msg(msg) -> str:
        text = (msg.raw_text or "").strip().replace("\n", " ")
        media = []
        if getattr(msg, "sticker", None):
            media.append("[стикер]")
        elif getattr(msg, "photo", None):
            media.append("[фото]")
        elif getattr(msg, "video", None):
            media.append("[видео]")
        elif getattr(msg, "video_note", None):
            media.append("[кружок]")
        elif getattr(msg, "voice", None):
            media.append("[голосовое]")
        elif getattr(msg, "gif", None):
            media.append("[гиф]")
        elif getattr(msg, "audio", None):
            media.append("[аудио]")
        elif getattr(msg, "document", None):
            media.append("[документ]")
        elif getattr(msg, "poll", None):
            media.append("[опрос]")
        elif getattr(msg, "geo", None) or getattr(msg, "geo_point", None):
            media.append("[гео]")
        elif getattr(msg, "contact", None):
            media.append("[контакт]")
        if text and media:
            return f"{text} {' '.join(media)}"
        if media:
            return " ".join(media)
        return text or None

    # ---------- message collection ----------

    async def _get_sender_name(self, sender_id):
        if sender_id not in self._sender_cache:
            try:
                ent = await self._client.get_entity(sender_id)
                self._sender_cache[sender_id] = get_display_name(ent) or str(sender_id)
            except Exception:
                self._sender_cache[sender_id] = str(sender_id)
        return self._sender_cache[sender_id]

    async def _collect_user_msgs(self, chat_id, sender_id, count):
        """Собирает РОВНО count сообщений юзера (текст + медиа-плейсхолдеры)."""
        msgs = []
        last_id = 0
        while len(msgs) < count:
            batch = []
            fetched_any = False
            async for msg in self._client.iter_messages(
                chat_id, from_user=sender_id, limit=200, max_id=last_id
            ):
                fetched_any = True
                last_id = msg.id
                body = self._format_msg(msg)
                if body:
                    batch.append(body)
            if not fetched_any:
                break
            batch.reverse()
            msgs = batch + msgs
            last_id -= 1
        return msgs[:count]

    async def _collect_chat_msgs(self, chat_id, count):
        """Собирает РОВНО count сообщений чата + возвращает словарь {id: имя}."""
        msgs = []
        senders = {}
        last_id = 0
        while len(msgs) < count:
            batch = []
            fetched_any = False
            async for msg in self._client.iter_messages(
                chat_id, limit=200, max_id=last_id
            ):
                fetched_any = True
                last_id = msg.id
                body = self._format_msg(msg)
                if body:
                    name = await self._get_sender_name(msg.sender_id)
                    batch.append(f"[{name}]: {body}")
                    if msg.sender_id and msg.sender_id not in senders:
                        senders[msg.sender_id] = name
            if not fetched_any:
                break
            batch.reverse()
            msgs = batch + msgs
            last_id -= 1
        return msgs[:count], senders

    # ---------- argument parsing ----------

    async def _parse_target(self, message, args):
        """
        Разбирает цель: (sender_id, raw_name, username, display_name) или None.
        Приоритет: реплай > @username в аргсах > без цели (чат).
        """
        # 1) реплай
        reply = await message.get_reply_message()
        if reply and reply.sender_id:
            sender = await reply.get_sender()
            raw = get_display_name(sender) or "пользователь"
            uname = getattr(sender, "username", None) or ""
            return (reply.sender_id, raw, uname, utils.escape_html(raw))

        if not args:
            return None  # чат-режим

        parts = args.strip().split()
        # 2) ищем @username или ник в аргсах
        username = None
        for p in parts:
            if p.startswith("@"):
                username = p.lstrip("@")
                break
            if re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,30}$", p):
                username = p
                break

        if not username:
            return None  # чат-режим

        try:
            entity = await self._client.get_entity(username)
        except Exception:
            return "not_found"

        raw = get_display_name(entity) or username
        uname = getattr(entity, "username", None) or ""
        return (entity.id, raw, uname, utils.escape_html(raw))

    @staticmethod
    def _parse_count(args, default):
        if not args:
            return default
        for p in args.strip().split():
            if p.isdigit():
                return max(1, int(p))
        return default

    # ---------- safe answering ----------

    async def _safe_answer(self, msg, text, fallback_text="?"):
        trimmed = text.strip()[:4096]
        try:
            await utils.answer(msg, trimmed)
        except Exception:
            try:
                clean = re.sub(r"<[^>]+>", "", trimmed)
                await utils.answer(msg, clean)
            except Exception:
                try:
                    await msg.respond(trimmed)
                except Exception:
                    clean = re.sub(r"<[^>]+>", "", trimmed)
                    await msg.respond(
                        f"<b>Разбор {utils.escape_html(fallback_text)}</b>\n\n{clean[:4000]}"
                    )

    # ---------- commands ----------

    @loader.command(
        ru_doc="[@user] [кол-во] — Анализ человека по реплаю/нику или чата без реплая"
    )
    async def tldr(self, message):
        (
            "[@username] [count] — Reply=analyse person, "
            "@name=analyse by nick, no reply=analyse chat"
        )
        args = utils.get_args_raw(message) or ""
        target = await self._parse_target(message, args)

        if target == "not_found":
            username = ""
            for p in args.strip().split():
                if p.startswith("@") or re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,30}$", p):
                    username = p
                    break
            return await utils.answer(
                message,
                self.strings("user_not_found").format(
                    user=utils.escape_html(username)
                ),
            )

        count = self._parse_count(args, self.config["default_count"])

        if target is None:
            # ЧАТ-РЕЖИМ
            await self._do_chat_analysis(message, count)
        else:
            sender_id, raw_name, username, name = target
            await self._do_user_analysis(
                message, sender_id, raw_name, username, name, count
            )

    @loader.command(ru_doc="[кол-во] — Анализ последних сообщений всего чата")
    async def tldrchatcmd(self, message):
        """[count] — Analyse recent chat messages"""
        args = utils.get_args_raw(message) or ""
        count = self._parse_count(args, self.config["default_count"])
        await self._do_chat_analysis(message, count)

    @loader.command(ru_doc="Ответь на сообщение/файл с ключами — добавит в пул")
    async def klcmd(self, message):
        """Reply to a message or file with API keys — add them to the pool"""
        reply = await message.get_reply_message()
        if not reply:
            return await utils.answer(message, self.strings("kl_no_reply"))

        raw = ""

        # 1) Файл (документ) — скачать и прочитать
        doc = getattr(reply, "document", None)
        if doc:
            tmp = None
            try:
                fd, tmp = tempfile.mkstemp(suffix=".txt")
                os.close(fd)
                tmp = await reply.download_media(file=tmp)
                if tmp and os.path.isfile(tmp):
                    with open(tmp, "r", encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
            except Exception:
                pass
            finally:
                if tmp and os.path.isfile(tmp):
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass

        # 2) Текст сообщения
        if not raw:
            raw = reply.raw_text or getattr(reply, "text", "") or ""

        if not raw.strip():
            # пустой ответ = сбросить файлы ключей
            def clear_file(file_cfg):
                path = os.path.join(os.getcwd(), self.config[file_cfg])
                if os.path.isfile(path):
                    try:
                        open(path, "w").close()
                    except Exception:
                        pass

            clear_file("keys_file")
            clear_file("or_keys_file")
            return await utils.answer(message, self.strings("kl_cleared"))

        new_g = re.findall(r"AIza[0-9A-Za-z_-]{15,}", raw)
        new_or = re.findall(r"sk-or-v1-[0-9a-fA-F]{30,}", raw)
        if not new_g and not new_or:
            return await utils.answer(message, self.strings("kl_no_keys"))

        def add_to_file(file_cfg, pattern, new_keys):
            path = os.path.join(os.getcwd(), self.config[file_cfg])
            existing = set()
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for k in re.findall(pattern, f.read()):
                            existing.add(k)
                except Exception:
                    pass
            added = 0
            dupes = 0
            with open(path, "a", encoding="utf-8") as f:
                for k in new_keys:
                    if k not in existing:
                        f.write(k + "\n")
                        existing.add(k)
                        added += 1
                    else:
                        dupes += 1
            return added, dupes, len(existing)

        g_added, g_dupes, g_total = add_to_file(
            "keys_file", r"AIza[0-9A-Za-z_-]{15,}", new_g
        )
        or_added, or_dupes, or_total = add_to_file(
            "or_keys_file", r"sk-or-v1-[0-9a-fA-F]{30,}", new_or
        )

        await utils.answer(
            message,
            self.strings("kl_added").format(
                g_added=g_added, g_dupes=g_dupes, g_total=g_total,
                or_added=or_added, or_dupes=or_dupes, or_total=or_total,
            ),
        )

    @loader.command(ru_doc="[@user1] @user2 [кол-во] — Сравнить двух людей в чате")
    async def tldrcmpcmd(self, message):
        (
            "[@user1] @user2 [count] — Compare two users. "
            "Reply to first user's message + .tldrcmp @user2"
        )
        args = utils.get_args_raw(message) or ""
        reply = await message.get_reply_message()

        # собираем цель 1: реплай либо первый юзернейм из аргсов
        target1 = None
        if reply and reply.sender_id:
            sender = await reply.get_sender()
            raw = get_display_name(sender) or "пользователь"
            uname = getattr(sender, "username", None) or ""
            target1 = (reply.sender_id, raw, uname, utils.escape_html(raw))

        # ищем юзернеймы в аргсах
        parts = args.strip().split()
        usernames = []
        for p in parts:
            if p.startswith("@"):
                usernames.append(p.lstrip("@"))
            elif re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,30}$", p) and not p.isdigit():
                usernames.append(p)

        count = self._parse_count(args, self.config["default_count"])

        if not target1 and len(usernames) >= 1:
            try:
                ent = await self._client.get_entity(usernames[0])
                raw = get_display_name(ent) or usernames[0]
                uname = getattr(ent, "username", None) or ""
                target1 = (ent.id, raw, uname, utils.escape_html(raw))
                usernames = usernames[1:]
            except Exception:
                return await utils.answer(
                    message,
                    self.strings("user_not_found").format(user=utils.escape_html(usernames[0])),
                )

        if not target1 or not usernames:
            return await utils.answer(message, self.strings("cmp_no_targets"))

        # цель 2: следующий юзернейм
        target2 = None
        try:
            ent = await self._client.get_entity(usernames[0])
            raw2 = get_display_name(ent) or usernames[0]
            uname2 = getattr(ent, "username", None) or ""
            target2 = (ent.id, raw2, uname2, utils.escape_html(raw2))
        except Exception:
            return await utils.answer(
                message,
                self.strings("user_not_found").format(user=utils.escape_html(usernames[0])),
            )

        sid1, raw1, un1, name1 = target1
        sid2, raw2, un2, name2 = target2

        msg = await utils.answer(
            message,
            self.strings("cmp_collecting").format(
                name1=name1, c1="...", name2=name2, c2="..."
            ),
        )

        msgs1 = await self._collect_user_msgs(message.chat_id, sid1, count)
        msgs2 = await self._collect_user_msgs(message.chat_id, sid2, count)

        if not msgs1 and not msgs2:
            return await utils.answer(msg, self.strings("no_msgs").format(name=f"{name1} + {name2}"))

        num1 = [f"{i + 1}. {t}" for i, t in enumerate(msgs1)]
        num2 = [f"{i + 1}. {t}" for i, t in enumerate(msgs2)]

        await utils.answer(
            msg,
            self.strings("cmp_analyzing").format(
                name1=name1, c1=len(msgs1), name2=name2, c2=len(msgs2)
            ),
        )

        try:
            raw = await self._ask_ai(
                self._build_cmp_prompt(raw1, raw2, num1, num2)
            )
        except Exception as e:
            return await self._safe_answer(
                msg,
                self.strings("error").format(error=utils.escape_html(str(e))),
                fallback_text="сравнение",
            )

        body = self._sanitize(raw)
        body = self._linkify_names(body, {sid1: raw1, sid2: raw2})
        header = self.strings("cmp_header").format(
            name1=name1, name2=name2, c1=len(msgs1), c2=len(msgs2),
            sid1=sid1, sid2=sid2,
        )
        await self._safe_answer(msg, header + body, fallback_text=f"{name1} vs {name2}")

    async def _do_user_analysis(
        self, message, sender_id, raw_name, username, display_name, count
    ):
        msg = await utils.answer(
            message, self.strings("collecting").format(name=display_name)
        )

        msgs = await self._collect_user_msgs(
            message.chat_id, sender_id, count
        )

        if not msgs:
            return await utils.answer(
                msg, self.strings("no_msgs").format(name=display_name)
            )

        numbered = [f"{i + 1}. {t}" for i, t in enumerate(msgs)]

        await utils.answer(
            msg,
            self.strings("analyzing").format(name=display_name, count=len(msgs)),
        )

        try:
            raw = await self._ask_ai(
                self._build_user_prompt(raw_name, username, numbered)
            )
        except Exception as e:
            return await self._safe_answer(
                msg,
                self.strings("error").format(error=utils.escape_html(str(e))),
                fallback_text="ошибка",
            )

        body = self._sanitize(raw)
        body = self._linkify_names(body, {sender_id: raw_name})
        header = self.strings("header_user").format(
            name=display_name, count=len(msgs), sender_id=sender_id
        )
        await self._safe_answer(msg, header + body, fallback_text=display_name)

    async def _do_chat_analysis(self, message, count):
        msg = await utils.answer(message, self.strings("collecting_chat"))

        msgs, senders = await self._collect_chat_msgs(message.chat_id, count)

        if not msgs:
            return await utils.answer(msg, self.strings("no_msgs_chat"))

        numbered = [f"{i + 1}. {t}" for i, t in enumerate(msgs)]

        await utils.answer(
            msg,
            self.strings("analyzing_chat").format(count=len(msgs)),
        )

        try:
            raw = await self._ask_ai(self._build_chat_prompt(numbered))
        except Exception as e:
            return await self._safe_answer(
                msg,
                self.strings("error").format(error=utils.escape_html(str(e))),
                fallback_text="ошибка",
            )

        body = self._sanitize(raw)
        body = self._linkify_names(body, senders)
        header = self.strings("header_chat").format(count=len(msgs))
        await self._safe_answer(msg, header + body, fallback_text="чат")
