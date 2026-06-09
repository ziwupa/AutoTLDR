# AutoTLDR — AI Userbot Module for Heroku

AI-анализ сообщений через Gemini / OpenRouter / OpenAI.

## Команды

| Команда | Описание |
|---------|----------|
| `.tldr` | В реплае — разбор человека. Без реплая — анализ чата |
| `.tldr @user` | Анализ пользователя по юзернейму |
| `.tldr 50` | Указать кол-во сообщений |
| `.tldrchat` | Анализ последних сообщений всего чата |
| `.tldrcmp @a @b` | Сравнить двух людей |
| `.kl` | Ответь на файл с ключами — добавит в пул. Пустой ответ — очистит пул |

## Конфиг

```
provider: gemini / openrouter / openai
gemini_api_key: ключ Gemini (Hidden)
openrouter_api_key: ключ OpenRouter (Hidden)
openai_api_key: ключ OpenAI (Hidden)
gemini_model: gemini-3.1-pro-preview
keys_file: gemini_keys.txt (файл с пулом Gemini-ключей)
or_keys_file: openrouter_keys.txt (файл с пулом OpenRouter-ключей)
openrouter_model: openai/gpt-4o-mini
openai_model: gpt-5.5
default_count: 100
allow_swearing: True
```

## Установка

1. Скачай `AutoTLDR.py`
2. Отправь в `loaded_modules/` (или ответь `.lm` на файл)
3. Настрой ключи через `.config AutoTLDR`

## Фичи

- Ротация ключей при 429 (round-robin)
- Плейсхолдеры для медиа: `[стикер]`, `[фото]`, `[голосовое]` и т.д.
- Кликабельные ссылки на профили в никах
- Мат регулируется тумблером `allow_swearing`
- Защита от гео-блоков через OpenRouter
- Пул ключей не хранится в .py — только во внешнем файле
