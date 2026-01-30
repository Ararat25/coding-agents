# Обход гео-ограничений OpenAI (403 unsupported_country_region_territory)

Если в твоём регионе OpenAI возвращает `403 - Country, region, or territory not supported`, можно сделать одно из двух.

---

## Вариант 1: Использовать YandexGPT (рекомендуется)

Сервис уже умеет работать с YandexGPT. Не нужен VPN и прокси.

1. В `.env` задай:
   ```env
   LLM_PROVIDER=yandex
   YANDEX_API_KEY=твой_ключ
   YANDEX_FOLDER_ID=id_каталога_в_yandex_cloud
   ```
2. Получить ключ и folder_id: [Yandex Cloud Console](https://console.cloud.yandex.ru/) → сервис YandexGPT / Foundation Models.
3. Перезапусти контейнер: `docker-compose up -d --build`.

Запросы к LLM пойдут в Yandex, без ограничений по стране.

---

## Вариант 2: OpenAI через прокси или зеркало API

Если нужен именно OpenAI, запросы можно пустить через прокси или сервис-зеркало с OpenAI-совместимым API.

### 2a) HTTP/HTTPS прокси (VPN на уровне прокси)

Если есть прокси в разрешённой стране (например корпоративный или платный VPN с режимом прокси):

В `.env`:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=твой_ключ
HTTPS_PROXY=http://127.0.0.1:7890
```
или
```env
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
```

Перезапусти контейнер. Все запросы к OpenAI пойдут через этот прокси.

### 2b) Зеркало / прокси OpenAI API (другой URL того же API)

Некоторые сервисы отдают тот же OpenAI API с другого домена (в т.ч. в обход гео). Если у тебя есть такой URL (например `https://api.openai-proxy.com/v1`):

В `.env`:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=твой_ключ
OPENAI_BASE_URL=https://api.openai-proxy.com/v1
```

`OPENAI_BASE_URL` должен заканчиваться на `/v1` (без слэша в конце). Перезапусти контейнер.

---

## Итог

| Решение              | Что задать в .env                          | Плюсы                          |
|----------------------|--------------------------------------------|--------------------------------|
| **YandexGPT**        | `LLM_PROVIDER=yandex`, ключ и folder_id     | Без прокси, уже встроено       |
| **Прокси для OpenAI**| `HTTPS_PROXY=...` или `HTTP_PROXY=...`      | Обычный OpenAI через VPN/прокси |
| **Зеркало API**      | `OPENAI_BASE_URL=https://.../v1`           | Тот же API с другого домена    |

Рекомендация: в первую очередь попробовать **YandexGPT** (вариант 1).

---

## Если YandexGPT возвращает 403 (Permission denied)

Ошибка вида:
```text
Permission to [resource-manager.folder ..., resource-manager.cloud ...] denied
```
означает, что у **API-ключа или сервисного аккаунта нет прав** на использование Foundation Models (YandexGPT) в указанном каталоге.

### Что сделать в Yandex Cloud

1. Зайди в [Yandex Cloud Console](https://console.cloud.yandex.ru/).
2. Выбери **каталог**, ID которого указан в `YANDEX_FOLDER_ID` (в твоей ошибке это `b1grm7pt842k26uoa9ng`).
3. **Права для API-ключа:**
   - Если используешь **API-ключ сервисного аккаунта**: зайди в **Service accounts** → выбери сервисный аккаунт, ключ которого в `YANDEX_API_KEY` → вкладка **Roles**. Должна быть роль **`ai.languageModels.user`** на уровне каталога (или облака).
   - Если такой роли нет: в каталоге открой **Access management** (Управление доступом) → найди нужный сервисный аккаунт (или пользователя) → **Assign role** → выбери роль **AI — Пользователь языковых моделей** (`ai.languageModels.user`).
4. **Включи Foundation Models для каталога:**
   - В меню слева: **AI Foundation Models** (или перейди в сервис [Foundation Models](https://yandex.cloud/en/services/foundation-models)).
   - Убедись, что сервис **подключён для этого каталога** и модель YandexGPT доступна (могут быть ограничения по региону/квоте).
5. Пересоздай API-ключ при необходимости: Service account → Create API key → скопируй ключ в `YANDEX_API_KEY`.

### Кратко

- **Роль:** у субъекта (сервисный аккаунт или пользователь), от которого создан API-ключ, должна быть **`ai.languageModels.user`** на каталог (или облако).
- **Каталог:** `YANDEX_FOLDER_ID` должен совпадать с ID каталога, в котором включён Foundation Models и выданы права.
- После смены прав подожди 1–2 минуты и повтори запрос.
