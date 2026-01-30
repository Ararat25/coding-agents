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
