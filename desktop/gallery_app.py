#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo Gallery - приложение для галерей выбора фото.

Выбираешь папку -> приложение делает превью, грузит фото в облако (Cloudflare R2),
публикует страницу и даёт ссылку. Клиент отмечает фото галочками (можно с комментариями),
выбор приходит через Worker (приложение подхватывает его само) или в Telegram. Выбранные фото
копируются в папку на компьютере. Готовые фото выдаются клиенту отдельной страницей с ZIP.

Запуск:   python gallery_app.py        (нужно: pip install pillow boto3)
В .exe:   build_exe.bat
"""
import base64
from html import escape as html_escape
import concurrent.futures as cf
import io
import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

APP_NAME = "PhotoGallery"
APP_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAASgklEQVR42uWbe7Bd9VXHP+v323uf9+Pem+SGkAtJICEFKhQLEbA8"
    "a51pwVYUa6t11NqZjlOtOtOqY1uwWrUva52O0qd9QwWLldqHM6AYMCWU0lD6EPIiJCE3ufeexz3vvX+/5R9735tLSpsEwkjJzuw5"
    "Z/bZOeeu7289vuu7flt46sMAmp28ZN3kVSryC4peqrAWpA5YnluHA20K7BLkXlH9t807p+/KPpPs9Ef+JznywvVgbwUHcMmZK39d"
    "lDchsskIqIKqpqg8Bw8BRAQR8Aqo3qfCh/5n+4HPHmnbUwJwOQR3Q7Jp3bL1gQlussZcpao4ryg4OYykPEcxSM0GFbDWCCKC8/6u"
    "xCdvvG/nzKMLNv4QAAsfXLxuxdXWmC+ImInE+QTBSBoSP3GHgkfxgTWBqp913r96y86Ddy4FwSy4Rmr85FVGzL+DTCTOJyIEP6nG"
    "Z6trRAgS5xOQCSPm3y9eN3nV3ZBcn+UwWUh4F502uSaM5FuC1J2qk+deknum3uCsiFW0GY/0gq17pncDYm7IbrABn7Iidec1eb4Z"
    "n620dV4TK1K3AZ8CuGEhB1y8bvJXw8DeHCep2/M8PlRJwsAEceJes2Xn9C3merACb1VVRZ6z2f1EuoKoqgq89XqwcukZk1cg5j9V"
    "VZ/D5e2EO4KICOqvNF7lOiNZyThZrAdvBDLb9VJVkJNn9RGQ1Ga91KiwNvX+n9x6/zQOo6qosDYAqT3b3N4Yk2VgXZKN9f87DACp"
    "PatMTySNqn6/j3qPsRZrLMYajDFZ4yJHlCl9ytdniykGx4SUKoj8+Jsku2/JqidJQpIknLlhPYVCgXarTafTod/rMRgOiUcxzjlU"
    "fVqfRDDGYKzBWosx2esCUE/6GzTNZurTn9XD65qh/9Tt7hFHcMxYHfH9qcFLLmpWZAWstSRJQrFU4m03vo1LX/KzRFZJhiM6vR7z"
    "8x1a7Q6NVovGXJO5uTkac3M05ho0Gg1azRbtdptup7sIVhInOO9RVUwGlLWGXD6PtQbn/JK/U4++aMcFgGQN5sJSyxGRZAxG0usu"
    "cfT7A1rtNu/923dz1XWvRA8eoDkwDH1EuZJj9fgyTgsErElpmKR1GO8gcTAc0usN6Ha7tNrzNJpNGo0ms7MNZmdnmZ09DNaOR3fS"
    "6/UpFos45447DIJjzhiSLftCx026CogwGg4ZDIYgwvhYjbM2nMFZG9Zx5Uuvxs/OcM9cntv25wHIG6VgoWg9ZeupBJ5ymL23SiVw"
    "lAOhHBYojRdZtmI5YrPuZFHX8RAn+GHMo7se5/3v/XseeGAbpVKRxLkM0GPLHXLJGSv1uHOAKsYahsMR3nmmpk7l3HNfwKafuZDz"
    "znsh9UqBxuwsq9aeRZeIG79fZpAoOSv4Ra1N8Jq+IkLKxCFAsXgio+SskjOeonFUrKNkHGXrqASOqnWclhuxYiyi3ejwW7/9JvY+"
    "vo8oivDeL0brM84BsiT0F77MBJZBf8CadWt485vfyPkvOo/yiklIYlpP7OeBezdzaKbB9RtfyOy84BQqYRoiIoLJcpRoFl7ZF3tV"
    "VMGrwSvMO2gl4BQcglcl8WllEFUqoeMNg/28cGqMV77qGt73ng+Sz+fxWQ6QExYCcrhLEiOoV4qlEn/1rrez/oLzaezcydZ/vZsD"
    "j+3i0L597Nq5i7UvuhjJ5enODjBiCG2qJRoRJEuWLCqVWUhlnrDgvRHQc+n1QBWvQsUmqd6HMjsKubM5wbmruqxatRJj7aInnbAc"
    "oEtAMEaw1jIzM8f5LzqP9Wetp7F7N1//zEdpTD9BEOVQsYRRjvEVK8AK84khsIbQ+sUqkdULzGJKkcWwVWRReI3VcHG5ydn5eQyw"
    "rVtia6eGwSMiFLK8IDag0+k9O0lQlmT5Xq/PYDhkxYplbLrwfDyGTrNBZ26WUrWGc57EeRKXUK7VAZh3FmuEIGODJvMmyfSqpUqm"
    "LFGeB2p4eXWal5SnUTWgcG65zapoxO2zK8iLQ0SoWA9GaLbaeO9/RPA+EwCM4JKEzmDAxo0buPaVr+Cyi36K0fwc3VaTseWTFKtV"
    "hr0eGJspyEJ1bBy80vGGyAhhxjeteWoAWMKjht6wJuxzSfEQfRdkRUcQB1fUmjzUr7FnkCMwSilIU2qj0XxaNDs4GpVNEkepWOTt"
    "N/wJV199OblCyPRMl/+aq3N+x3LuqiK15St5YucjBEGIqgNjqdXr4Dw9F5ILhMguAGAwApIxOQkC1CVZlUldIBHLVK6P4FHS+9MK"
    "LIhRTs+P2DMqEmhaRvFKs9lC5PhZvTkaAIPBgN//g9/l5a++jkEC9zfH2cIL2FveyO5OgISWZatPzyitkrgEG4SUazU08QzVkrNC"
    "aA250BIFhlCUXBhQKFcwox7FUomctURGiKwhZw0JAYtkNkucmvGQoVpCA6EVKoGC8zSbLYxZTNXHPLz5sQB47ykWi5x77tm4xiyP"
    "MckTwUqiMGA8p+zvCn7kmJxagzEW75UkTgiiHOVyhUGiJFjyGQCRNQTqyBcKhGHI9s++i/v++BXs+Px7KJRKRFYIrVAOlAO+RtPn"
    "yOsI7xWnUJCYmSTisVGJolWsEcqhQuJot+exxiy6v5wIAKwxdDtdvr3tYWw+T6gxkXisgXIhR8uFzHVGLD9lJblyFefS5ifMFymW"
    "ivQSUBMsGhZoQqlaR7tNHnz3G9j95Y/jRgN2funDbL/lvZSqVUIDeQtqQu4erWPO5wmICXXEdJzny+0pYgmJrBBZoRyAj2M6nU7K"
    "TFUXK40+UwAUJQhDPvGJz9CabbImaFBkCGIp5UOczbGvnVCqVakvX0k8GhEnCaVKhSifp+cEjCE0pPE6Pk5n5za+ceNrmf3OveTr"
    "ywlsQH5sOY/efhO7vnQTlXqVQDylQGlLha8m5/C14QbuGJzFbZ31zPoiRasYY8hZKAXQH4zodnoYaw5PdE9MCCjFYoFHH9nOZz//"
    "LxQqOabcflQsucCQz+d4vGsgsCyfOo0kThjFCeXaGAQBfZeyvsgK5fE6++/+V/7nnb9B7+A+okodXIKgGJR8pc5Dn343u79+M7Xx"
    "GlYdResJRJiJTuGQrxDm8hTDtIcKjJC3UAyg2+3T6/Wwxi7tlJ85AADOOarVMp/77C3s2fE4q/M9atoBG1LJRzzRD/DDhMnVpyFB"
    "SJIkVOp1MNCPPVEuolAq873PvI/7/vYP8c5j80V8kixBOmVvuVKVb334Hezd/NUUBDy5SoXi9rsp3fqHFO/5GEEQEliLFShYyFul"
    "3enSHwwQc4KrwMIRRREzM3N85GOfJsyHnO72Y8RQLoS0XMhsd8TyyRXkS2XiUUx1fBxcjMvXMG7I1vf+Lt+9+YMEpSoYg/fuSbVf"
    "UdR7RAw2ynPvB/6I6QfvpbasSrL5c8Rf/QB05jAPf5385o8S5QsEgaUgCTmrzHc6JHGMiBxzE3RcAKj31GtV7vjSV/j2N7/DKeWE"
    "CW0Q5fJ4m2Nf21GulqlOLCeOY2r1MbAhh/bs5L/f/mvsuefLRLVxvHOo10UFR7N/XtNTvcMEAarKne9/C7s+fgN+6z9DVMDk8khp"
    "DPuDu7D/9WGGPiVIoglPHDhIs9kiDGw22zn2SmCOiQqLEASWOI75h5v+CUVYqwcoBEIY5djXM4g1LDt1Nc4r1XoNELZ87K9oPPIg"
    "UXUZSRzjMo6vquncemHDhc/eAz5x2ChP0mmy+fZbaLuQKAhQ7/EuphsLpd1buKj3LS6fSN1+atUkL77wAlrtDnE8wlp7AkMga2FR"
    "pV6rcs9/38udd25mogKn+INE+TzTgwCfeFacsoogl6dcrZB05mk0mgSFMkkSZ62u4rzHe49XspXnSZ8573FJggkChoRseehRusMR"
    "qDIaJVz0spdz3ZvfxjlrVzKKY+5vVqi94GK+cMvH+bsPvJPa2Bj9fh9zjCAcQzu8ZGAoEIYBN334k1x6yYtZZ0d8PyqwL8nR7LWY"
    "WDZOqTZOsVig02oyPz+frmpmqLBEV1F9ktDgfdrhLTiwOo8V6PaGbNm2nQvOXsu1r3s99Y0v5ouPC9+bD+gkQuIccRyzKjL8xhXX"
    "8MkzT+d33vgnzB48RJSLjmiQnmYILNBiVaVcKvHwQw/zxdu/QrUSssEepCMFpntKMR9y6to1FPJ5Wo05Op1utkXlsMS9YLf3Wewv"
    "aYK8Kk4Ph4ZTJYpC9h+c4cwLL2PihZfwkR8I32lHGKBoHAVx5Aw80o34028og8mz+et3/AHuRIXA0s4qzbJKuVTkk5/8PIcOzLKx"
    "0GAsiNndSdve9Rs3EIWGubkGvf5giQekbu4zN1+a/FwWEqqp3LdwHaDT7bLxnHN46TXXcvMPRsy5kIJJSLwndunZSzyTUQI24P3b"
    "POdt2sRVl1/M/HxncSjzjHLAk96qks/neXzPXj7zuX+hVM5xttnH/kGOeDTi1KlTCXJ5Zg8eJElijLWLQaRLev/DZ+oFTg8D4r3H"
    "pxuz6PcHXHHlZeyjzvfbgtWE1khJnMc5x9xQuWy55y9/2nNO1fNIx/Ktdp6fv3wTidcfGrwcPwD6FBqheqrVCrfe9iW2P/o4P1Xt"
    "or0WzdhQLBTw8YhTTl2FR2jMNen2evQHQ0bZICQtgAvCoKTTImNT4cWYrJtTnPOYIGTDWWfxSFMZuLRUrogcnZFjZqBcscLx2vWe"
    "fW3PY+2YEOX7DZiaWkkulztqDrBT4+Ubj80L5EkTlzAIaDQaDEYxL7vsIhoH9pIvlYlGbXKVOpPLJzjt9NUoysTEOKViniiKUAXn"
    "EuJRzGAwYDhIJfV4NCIexcRxgnMuqxRp2Lzqumt5PDqVBw7FbJpQ3rgxZroHKwvK6zd6dsw5/vybI9pxKpyurypr4/3cdsedBEZO"
    "xGSITMiWxRGBz8jRV792J6942RVMFQOkN4cLAw7t38vkqlVc+dIrufJlV0KcMIpj+v0+/V6fbqdLu92m1Zqn1WrRarZpt9q02m3a"
    "7Xk68x263XQi1J7v0pyboziRIKpsm/W8ZLnym2emaW73nOOd9w/o+IBioLRHylRJObRrhuFwSCEqoT/GC457P5AseIGmWmE86vGp"
    "z93GW37vN5k5NMPa9etpHjrInh09olwOEYMJAnJRRLGYp1YtU6/XOKN0JuRyEIawsA01cRDH+H6fbjcdoe3avp1qMaIctAmkwMGe"
    "428eUv7sPIN65catA+Z9QMEqQ6cUrefC8YRP3P8QZKX1hE2GlCXbiARQT7VSYst9D/DQ1T/LutWTfG/bNlasXEnjwDTtZhP1Kf09"
    "ONvgkV37+N72xxjGjlqtQq1aZXyszvh4jWXjY4xPjDFerzE2VqNeq1IuF9m4cQPz7TbrCh0uKHvumi2QJAnv+KZLtUpnKAaexCuH"
    "+vCG9Q4zs4c7/uMeyqXCUXNAcBwRkG2uSUGQhaAQwRrDzbd9mff9xVux1tCYnSGwlnK5wo7de7n/29/l4R/spNFqp4MRgX1792fZ"
    "3i+WPJFMQo9CcrkcpUKBcrmId47XvPqVvOn1r+PQfW3ub+YJRLGS6oXNkTKIPdetHvHa9fCWP/ooszMz1GvVo0rlRx2N/Uh6nOUD"
    "1bTUzHe6XLzpAl73q6/CWuHh7z7Cf27eyv9u381wNCKfi4jCYJFbSKbz8eSJWzru9hk3cBk1dilIN/7Z7/Mrv/bL3LnXctcTMDNM"
    "F2J1SblmSjm/0uVdf/MhbvnnO6jXynh3dHnk6QGwpBosdHUpaekTRSG5XES7nZKQYiEdX2uW0X+IZMtSSVyXsM7D0n6qTifM9/r8"
    "wjU/x++85lqm1pyOD4sIHt9r8+C27/KPn7iVb297mHqtivpj04aOCQA9YtQgTzEy85rKVAskJrBmceh5tC+TJw1ij/yhhVFZelez"
    "PU8Y5Vhz+qmsmKiTOM++Jw6yb98BosBQKhXTvuIYByNP3wOOIqc/W1tbrDU4r4yGQ5IkHYVHYUAURYtK9nGNxhT8id4n9Gzu60l3"
    "gkAulyOfl8XfO17DF/cLgrZ+EjcI6mLP4J8W4Bl0LSPKrowsnDQ7RQEvIoiyyyhyb0bs9GSxXkFTm+VeY0S/mKk1J81OUQHjFYzo"
    "F82qHdOb1fsHrREU3Emw+s4aQb1/cNWO6c3m1nQLzntkQe55/iOgIiIK77kVnLkBzJad01+IE7c5tBKokjxvbVeS0EoQJ27zlp3T"
    "X7gh7UNP8oemAH89mK17pnd5r7+kqkMrYp9PnqBKktqkQ+/1l7bumd51fbrw/qR/cHLRzR8DfzkE9zS6O06p528XkXMCa84wkj5d"
    "kT06y3HOHv8fbE67agETGBFrjfHq70p88ovf2Hnomz/y0dmF46R+ePoIufykeHz+/wCPIOQyiN+DNwAAAABJRU5ErkJggg=="
)
APP_TITLE = "Photo Gallery - галереи выбора фото"

RAW_EXT = {".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw"}   # RAW: Sony ARW и др.
EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"} | RAW_EXT
CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
}
CONTENT_TYPES.update({e: "application/octet-stream" for e in RAW_EXT})
THUMB_SIZE = 700            # превью в сетке, px по длинной стороне
UPLOAD_WORKERS = 8
PHOTO_CACHE = "public, max-age=86400"
DEFAULT_TITLE = "Выберите понравившиеся фото"
DEFAULT_MESSAGE = (
    "Здравствуйте! Фото готовы: {link}\n"
    "Отметьте понравившиеся галочкой (кружок в углу фото), затем нажмите "
    "«Отправить выбор» внизу страницы. Ссылка личная, пожалуйста, не пересылайте её."
)
MODE_ORIGINAL = "original"
MODE_VIEW = "view"
MODE_LABELS = {
    MODE_ORIGINAL: "Оригиналы в облаке (клиент видит полный размер)",
    MODE_VIEW: "Только копии для просмотра (экономит место, оригиналы остаются у вас)",
}
R2_PRICE_PER_GB = 0.015     # $/ГБ в месяц (Cloudflare R2, Standard)
COMMENTS_MARK = "Комментарии к фото:"   # раздел сообщения клиента; формат строк: имя | текст
SERVICES_MARK = "Услуги по фото:"        # раздел сообщения клиента; формат строк: имя | услуга
SERVICES = {"color": "Цветокоррекция", "retouch": "Ретушь", "comment": "Комментарий"}   # они же имена папок
SERVICE_BY_NAME = {v.lower(): k for k, v in SERVICES.items()}
COMMENTS_FILE = "комментарии_к_фото.txt"
INBOX_DIR = "_inbox"       # сюда Worker складывает выборы клиентов
STATS_DIR = "_stats"       # и статистику просмотров
FINAL_DIR = "_final"       # страница выдачи готовых фото: <slug>/_final/
PF_SLUG = "_portfolio"     # страница портфолио: _portfolio/index.html
REVIEWS_DIR = "_reviews"   # отзывы клиентов, ждущие проверки (их кладёт Worker)
FINAL_TITLE = "Ваши готовые фото"
DEFAULT_FINAL_MESSAGE = (
    "Здравствуйте! Ваши готовые фото: {link}\n"
    "Можно скачать всё одним архивом (кнопка вверху) или каждое фото отдельно. "
    "Ссылка личная, пожалуйста, не пересылайте её."
)
AUTO_CHECK_MS = 180_000    # как часто искать новые выборы, пока приложение открыто

WORKER_SOURCE = r"""// Photo Gallery Worker: принимает выбор клиента, отзывы и статистику просмотров.
// Токен Telegram (если нужен) хранится здесь, а не на странице клиента.
//
// Настройки Worker (Settings -> Bindings / Variables and Secrets):
//   BUCKET        (R2 bucket binding)  обязательно: тот же бакет, что и в приложении
//   TG_TOKEN      (Secret)             необязательно: токен бота для уведомлений
//   TG_CHAT       (Text)               необязательно: ваш Chat ID
//   ALLOW_ORIGIN  (Text)               необязательно: адрес бакета, например https://pub-xxxx.r2.dev

const SLUG = /^[a-z0-9][a-z0-9_-]{0,60}$/;
const MAX_BODY = 300000;      // байт
const MAX_INBOX = 200;        // максимум выборов на одну галерею (защита от спама)
const MAX_REVIEWS = 5;        // максимум неразобранных отзывов от одной галереи

function cors(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function reply(env, obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...cors(env) },
  });
}

async function notify(env, text) {
  if (!env.TG_TOKEN || !env.TG_CHAT) return;
  try {
    await fetch("https://api.telegram.org/bot" + env.TG_TOKEN + "/sendMessage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: env.TG_CHAT,
        text: text.slice(0, 3900),
        disable_web_page_preview: true,
      }),
    });
  } catch (e) { /* уведомление не критично */ }
}

function clip(v, n) {
  return String(v == null ? "" : v).slice(0, n);
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }
    const url = new URL(request.url);

    if (request.method === "GET") {
      if (url.pathname === "/ping") {
        let r2 = false;
        try { await env.BUCKET.list({ limit: 1 }); r2 = true; } catch (e) { /* нет привязки */ }
        return reply(env, { ok: true, r2: r2, telegram: !!(env.TG_TOKEN && env.TG_CHAT) });
      }
      return reply(env, { ok: true, service: "photo-gallery" });
    }
    if (request.method !== "POST") return reply(env, { ok: false, error: "method" }, 405);
    if (!env.BUCKET) return reply(env, { ok: false, error: "no BUCKET binding" }, 500);

    const raw = await request.text();
    if (raw.length > MAX_BODY) return reply(env, { ok: false, error: "too large" }, 413);
    let d;
    try { d = JSON.parse(raw); } catch (e) { return reply(env, { ok: false, error: "bad json" }, 400); }
    if (!d || typeof d !== "object") return reply(env, { ok: false, error: "bad json" }, 400);

    const slug = String(d.slug || "");
    if (!SLUG.test(slug)) return reply(env, { ok: false, error: "bad gallery" }, 400);
    // принимаем данные только для галерей, которые реально опубликованы
    const page = await env.BUCKET.head(slug + "/index.html");
    if (!page) return reply(env, { ok: false, error: "unknown gallery" }, 404);

    const now = new Date().toISOString();

    if (url.pathname === "/sel") {
      const text = String(d.text || "");
      if (text.length < 10) return reply(env, { ok: false, error: "empty" }, 400);
      const prefix = "_inbox/" + slug + "/";
      const listed = await env.BUCKET.list({ prefix: prefix, limit: MAX_INBOX + 1 });
      if (listed.objects.length > MAX_INBOX) return reply(env, { ok: false, error: "inbox full" }, 429);
      const rnd = crypto.randomUUID().replace(/-/g, "").slice(0, 10);
      const key = prefix + Date.now() + "-" + rnd + ".json";
      const rec = {
        t: now,
        client: clip(d.client, 100),
        count: Number(d.count) || 0,
        text: text,
      };
      await env.BUCKET.put(key, JSON.stringify(rec), {
        httpMetadata: { contentType: "application/json" },
      });
      ctx.waitUntil(notify(env,
        "📸 Новый выбор: " + rec.client + " (" + rec.count + " фото)\n" +
        "Галерея: " + clip(d.gallery, 60) + "\n" +
        "Открой приложение -> «Выбор клиента» -> «Проверить новые выборы»."));
      return reply(env, { ok: true });
    }

    if (url.pathname === "/review") {
      const text = clip(d.text, 1500).trim();
      if (text.length < 10) return reply(env, { ok: false, error: "empty" }, 400);
      const prefix = "_reviews/" + slug + "/";
      const listed = await env.BUCKET.list({ prefix: prefix, limit: MAX_REVIEWS + 1 });
      if (listed.objects.length >= MAX_REVIEWS) return reply(env, { ok: false, error: "limit" }, 429);
      const rating = Math.max(1, Math.min(5, Math.round(Number(d.rating)) || 5));
      const rnd = crypto.randomUUID().replace(/-/g, "").slice(0, 10);
      const rec = { t: now, author: clip(d.author, 60).trim(), rating: rating, text: text };
      await env.BUCKET.put(prefix + Date.now() + "-" + rnd + ".json", JSON.stringify(rec), {
        httpMetadata: { contentType: "application/json" },
      });
      ctx.waitUntil(notify(env,
        "⭐ Новый отзыв (" + rating + "/5) от " + (rec.author || "клиента") + "\n" +
        "Открой приложение -> «Портфолио» -> «Отзывы» -> «Проверить новые»."));
      return reply(env, { ok: true });
    }

    if (url.pathname === "/view") {
      const key = "_stats/" + slug + ".json";
      let st = {};
      try {
        const obj = await env.BUCKET.get(key);
        if (obj) st = await obj.json();
      } catch (e) { st = {}; }
      st.views = Number(st.views) || 0;
      let first = false;
      if (d.event === "open") {
        st.views += 1;
        if (!st.first) { st.first = now; first = true; }
      } else if (d.event === "leave") {
        st.selected = Math.max(0, Math.min(100000, Number(d.selected) || 0));
        st.comments = Math.max(0, Math.min(100000, Number(d.comments) || 0));
      } else {
        return reply(env, { ok: false, error: "bad event" }, 400);
      }
      st.last = now;
      // уведомляем при первом открытии и не чаще раза в 6 часов
      let ping = false;
      if (d.event === "open") {
        const prev = st.lastNotify ? Date.parse(st.lastNotify) : 0;
        if (first || Date.now() - prev > 6 * 3600 * 1000) { ping = true; st.lastNotify = now; }
      }
      await env.BUCKET.put(key, JSON.stringify(st), {
        httpMetadata: { contentType: "application/json" },
      });
      if (ping) {
        ctx.waitUntil(notify(env,
          "👀 Клиент " + (first ? "впервые открыл" : "снова открыл") + " галерею " + slug +
          " (открытий: " + st.views + ")"));
      }
      return reply(env, { ok: true });
    }

    return reply(env, { ok: false, error: "not found" }, 404);
  },
};
"""

DELIVERY_TEMPLATE = r"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#3E2C23"><title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&family=Playfair+Display:wght@500&display=swap" rel="stylesheet">
<style>
:root{--bg:#3E2C23;--card:#5B4133;--field:#4A362B;--text:#EFE3D8;--muted:#B9A08F;--light:#E6F4FB;--blue:#A7D8F0;--blue-h:#75C0E6;--on-blue:#2B1D16}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Montserrat,system-ui,-apple-system,"Segoe UI",sans-serif;padding-bottom:40px}
.hero{max-width:1500px;margin:0 auto;padding:28px 20px 8px}
h1{font-family:"Playfair Display",Georgia,serif;font-weight:500;font-size:clamp(26px,4.6vw,44px);margin:0 0 8px;color:var(--light)}
.sub{color:var(--muted);font-size:14px}
.pf{display:inline-block;margin-top:12px;color:var(--blue);font-size:14px;font-weight:600;text-decoration:none}
.pf:hover{color:var(--blue-h)}
.zip{display:block;max-width:560px;margin:14px 20px 18px;padding:18px;border-radius:16px;background:var(--blue);color:var(--on-blue);
  text-align:center;font-size:17px;font-weight:700;text-decoration:none}
.zip:hover{background:var(--blue-h)}
.zip small{display:block;font-weight:500;opacity:.8;margin-top:3px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;padding:0 14px;max-width:1500px;margin:0 auto;align-items:start}
.item{background:var(--card);border-radius:16px;overflow:hidden}
.item a.pic{display:block;aspect-ratio:3/2;background:#2c1f18}
.item img{width:100%;height:100%;object-fit:cover;display:block}
.row{display:flex;gap:8px;padding:9px 10px;align-items:center;justify-content:space-between}
.nm{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
a.dl{background:var(--field);color:var(--text);border-radius:10px;padding:8px 12px;font-size:13px;font-weight:600;text-decoration:none;white-space:nowrap}
a.dl:hover{background:#6E5141}
@media (max-width:640px){.grid{grid-template-columns:repeat(2,1fr);gap:8px;padding:0 8px}.zip{margin:12px 12px 16px}.hero{padding:20px 16px 6px}}
</style></head><body>
<header class="hero"><h1>__TITLE__</h1>
<div class="sub" id="sub"></div>
<a class="pf" id="pf" hidden href="../../_portfolio/index.html?g=__SLUG__#reviews">Портфолио и отзывы →</a></header>
<a class="zip" id="zip" href="#" style="display:none" download></a>
<div class="grid" id="grid"></div>
<script>
const PHOTOS=__PHOTOS__, ZIP=__ZIP__, ZIPSIZE=__ZIPSIZE__;
if(__PORTFOLIO__)document.getElementById("pf").hidden=false;
const fileName=p=>{try{return decodeURIComponent(p.f.split("/").pop())}catch(e){return p.f.split("/").pop()}};
document.getElementById("sub").textContent="Фото: "+PHOTOS.length+". Можно скачать по одному или всё сразу.";
if(ZIP){
  const z=document.getElementById("zip");
  z.href=ZIP;z.style.display="block";z.setAttribute("download","");
  z.innerHTML="⬇ Скачать все фото одним архивом<small>"+ZIPSIZE+"</small>";
}
const grid=document.getElementById("grid");
PHOTOS.forEach(p=>{
  const it=document.createElement("div");it.className="item";
  const a=document.createElement("a");a.className="pic";a.href=p.f;a.target="_blank";a.rel="noopener";
  const im=document.createElement("img");im.loading="lazy";im.src=p.t;im.alt="";a.appendChild(im);
  const row=document.createElement("div");row.className="row";
  const nm=document.createElement("div");nm.className="nm";nm.textContent=p.n;
  const d=document.createElement("a");d.className="dl";d.textContent="⬇ Скачать";d.href=p.f;d.download=fileName(p);
  row.appendChild(nm);row.appendChild(d);
  it.appendChild(a);it.appendChild(row);grid.appendChild(it);
});
</script></body></html>
"""

PORTFOLIO_TEMPLATE = r"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#3E2C23">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&family=Playfair+Display:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#3E2C23;--card:#5B4133;--field:#4A362B;--border:#6B4F3F;--second:#87634F;
  --text:#EFE3D8;--beige:#D9C3B1;--muted:#B9A08F;--light:#E6F4FB;
  --blue:#A7D8F0;--blue-h:#75C0E6;--on-blue:#2B1D16;
  --body:Montserrat,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --head:"Playfair Display",Georgia,"Times New Roman",serif;
  --safe:env(safe-area-inset-bottom,0px);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
[hidden]{display:none!important}
html{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--body);font-size:15px;line-height:1.5;
  padding-bottom:calc(40px + var(--safe))}
button,input,textarea{font-family:inherit}
button{cursor:pointer;border:0}
.hero{max-width:1400px;margin:0 auto;padding:26px 20px 10px}
.back{display:inline-block;color:var(--blue);text-decoration:none;font-size:14px;font-weight:500;margin-bottom:14px}
.back:hover{color:var(--blue-h)}
.hero h1{font-family:var(--head);font-weight:500;font-size:clamp(30px,5.4vw,54px);line-height:1.1;margin:0 0 10px;color:var(--light)}
.about{margin:0;color:var(--beige);font-size:15px;max-width:720px;white-space:pre-line}
.contacts{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.btn{border-radius:12px;padding:10px 16px;font-size:14px;font-weight:600;transition:.15s;display:inline-flex;
  align-items:center;gap:8px;text-decoration:none;white-space:nowrap}
.btn.primary{background:var(--blue);color:var(--on-blue)}
.btn.primary:hover{background:var(--blue-h)}
.btn.line{background:transparent;color:var(--text);border:1px solid var(--border)}
.btn.line:hover{background:rgba(255,255,255,.06)}
.btn:disabled{opacity:.55;cursor:default}
.tabs{position:sticky;top:0;z-index:5;background:rgba(62,44,35,.93);backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);border-bottom:1px solid rgba(107,79,63,.6)}
.tabs-in{max-width:1400px;margin:0 auto;padding:8px 20px;display:flex;gap:6px}
.tabs button{background:transparent;color:var(--muted);padding:10px 18px;border-radius:12px;font-size:15px;font-weight:600}
.tabs button:hover{color:var(--text)}
.tabs button.on{background:var(--card);color:var(--light)}
.tabs small{opacity:.7;font-weight:500;margin-left:4px}
.wrap{max-width:1400px;margin:0 auto;padding:16px 14px 0}
.grid{columns:3 280px;column-gap:12px}
.item{break-inside:avoid;margin:0 0 12px;border-radius:16px;overflow:hidden;background:#2c1f18;cursor:zoom-in;
  box-shadow:0 2px 10px rgba(0,0,0,.18);display:block;width:100%;padding:0}
.item img{width:100%;height:auto;display:block;transition:transform .35s}
@media (hover:hover){.item:hover img{transform:scale(1.03)}}
.item{position:relative}
.rv-head{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.avg{display:flex;align-items:center;gap:12px;color:var(--beige);font-size:14px}
.avg b{font-family:var(--head);font-size:40px;font-weight:500;color:var(--light);line-height:1}
.stars{color:#F2C66B;letter-spacing:2px;font-size:17px;white-space:nowrap}
.stars i{font-style:normal;color:#6E5141}
.rv-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;align-items:start}
.rv{background:var(--card);border-radius:18px;padding:20px 20px 18px;box-shadow:0 2px 10px rgba(0,0,0,.18)}
.rv p{margin:10px 0 14px;color:var(--text);white-space:pre-line;overflow-wrap:anywhere}
.rv .who{display:flex;justify-content:space-between;gap:10px;align-items:baseline;color:var(--muted);font-size:13px}
.rv .who b{color:var(--light);font-size:15px;font-weight:600}
.empty{text-align:center;color:var(--muted);padding:60px 20px}
#lb{position:fixed;inset:0;z-index:20;background:#1c130e;display:none;flex-direction:column}
#lb.open{display:flex}
.lb-top{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;flex:none;color:var(--beige);font-size:14px}
.x{width:40px;height:40px;border-radius:50%;background:var(--card);color:var(--beige);font-size:18px}
.x:hover{background:#6E5141}
.stage{flex:1;min-height:0;position:relative;display:flex;align-items:center;justify-content:center;touch-action:pan-y;padding:0 0 calc(10px + var(--safe))}
.stage img{max-width:100%;max-height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none}
.nav{position:absolute;top:50%;transform:translateY(-50%);width:48px;height:64px;border-radius:14px;
  background:rgba(91,65,51,.7);color:var(--light);font-size:30px}
.nav:hover{background:var(--card)}
.nav.prev{left:10px}.nav.next{right:10px}
@media (max-width:640px){.nav{display:none}}
#dlg{position:fixed;inset:0;z-index:30;background:rgba(20,13,9,.72);display:none;align-items:center;
  justify-content:center;padding:16px;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px)}
#dlg.open{display:flex}
.box{position:relative;background:var(--bg);border:1px solid var(--border);border-radius:22px;padding:26px 22px 22px;
  width:100%;max-width:460px;max-height:92vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.box .x{position:absolute;top:12px;right:12px;width:38px;height:38px}
.box h2{font-family:var(--head);font-weight:500;font-size:26px;margin:0 36px 6px 0;color:var(--light)}
.box p{margin:0 0 12px;color:var(--beige);font-size:14px}
.box label{display:block;font-size:13px;color:var(--muted);margin:12px 0 6px}
.box input,.box textarea{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--border);
  background:var(--field);color:var(--text);font-size:16px;resize:vertical}
.box input:focus,.box textarea:focus{outline:none;border-color:var(--blue)}
.pick{display:flex;gap:4px}
.pick button{background:transparent;font-size:34px;line-height:1;color:#6E5141;padding:0 2px}
.pick button.on{color:#F2C66B}
.err{color:#F4B0A0;font-size:13px;min-height:18px;margin-top:8px}
.box .btn{width:100%;justify-content:center;margin-top:10px;padding:14px}
@media (max-width:640px){
  .hero{padding:18px 16px 6px}
  .tabs-in{padding:6px 12px}
  .wrap{padding:12px 8px 0}
  .grid{columns:2 140px;column-gap:8px}
  .item{margin-bottom:8px;border-radius:12px}
  .rv-list{grid-template-columns:1fr}
}
</style></head><body>

<header class="hero">
  <a class="back" id="back" hidden>← К моей галерее</a>
  <h1 id="ttl"></h1>
  <p class="about" id="about" hidden></p>
  <div class="contacts" id="contacts"></div>
</header>

<nav class="tabs"><div class="tabs-in" role="tablist">
  <button type="button" data-t="works" class="on" role="tab">Работы<small id="nW"></small></button>
  <button type="button" data-t="rev" role="tab">Отзывы<small id="nR"></small></button>
</div></nav>

<main class="wrap">
  <section id="works"><div class="grid" id="grid"></div></section>
  <section id="rev" hidden>
    <div class="rv-head">
      <div class="avg" id="avg"></div>
      <button class="btn primary" id="addRev" type="button" hidden>Оставить отзыв</button>
    </div>
    <div class="rv-list" id="rvList"></div>
    <div class="empty" id="rvEmpty" hidden>Отзывов пока нет.</div>
  </section>
</main>

<div id="lb" role="dialog" aria-modal="true" aria-label="Просмотр фото">
  <div class="lb-top"><span id="lbCnt"></span><button class="x" id="lbX" type="button" aria-label="Закрыть">✕</button></div>
  <div class="stage" id="stage">
    <button class="nav prev" id="lbP" type="button" aria-label="Назад">‹</button>
    <img id="lbImg" alt="">
    <button class="nav next" id="lbN" type="button" aria-label="Вперёд">›</button>
  </div>
</div>

<div id="dlg" role="dialog" aria-modal="true" aria-label="Оставить отзыв">
  <div class="box">
    <button class="x" id="dX" type="button" aria-label="Закрыть">✕</button>
    <div id="dForm">
      <h2>Ваш отзыв</h2>
      <p>Он появится на странице после проверки.</p>
      <label>Ваша оценка</label>
      <div class="pick" id="pick"></div>
      <label for="rvName">Имя</label>
      <input id="rvName" maxlength="60" autocomplete="name" placeholder="Как вас представить">
      <label for="rvText">Отзыв</label>
      <textarea id="rvText" rows="5" maxlength="1500" placeholder="Расскажите, как всё прошло"></textarea>
      <div class="err" id="rvErr"></div>
      <button class="btn primary" id="rvSend" type="button">Отправить отзыв</button>
    </div>
    <div id="dDone" hidden>
      <h2>Спасибо!</h2>
      <p>Отзыв отправлен. Он появится на странице после проверки.</p>
      <button class="btn line" id="dOk" type="button">Закрыть</button>
    </div>
  </div>
</div>

<script>
const D=__DATA__;
const $=id=>document.getElementById(id);
const SLUGRE=/^[a-z0-9][a-z0-9_-]{0,60}$/;
let G="";
try{G=(new URLSearchParams(location.search).get("g")||"").toLowerCase()}catch(e){}
if(!SLUGRE.test(G))G="";
const store={get(k){try{return localStorage.getItem(k)}catch(e){return null}},
  set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};

$("ttl").textContent=D.title||"Портфолио";
if(D.about){$("about").textContent=D.about;$("about").hidden=false}
(D.contacts||[]).forEach(c=>{
  const a=document.createElement("a");a.className="btn line";a.textContent=c.l;a.href=c.u;
  a.target="_blank";a.rel="noopener";$("contacts").appendChild(a);
});
if(G){$("back").href="../"+G+"/index.html";$("back").hidden=false}

/* вкладки */
function tab(t){
  $("works").hidden=t!=="works";$("rev").hidden=t!=="rev";
  document.querySelectorAll(".tabs button").forEach(b=>b.classList.toggle("on",b.dataset.t===t));
  try{history.replaceState(null,"",t==="rev"?"#reviews":location.pathname+location.search)}catch(e){}
}
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>tab(b.dataset.t));
$("nW").textContent=D.photos.length?String(D.photos.length):"";
$("nR").textContent=D.reviews.length?String(D.reviews.length):"";

/* работы */
const grid=$("grid");
D.photos.forEach((p,i)=>{
  const b=document.createElement("button");b.className="item";b.type="button";b.setAttribute("aria-label","Открыть фото "+(i+1));
  const im=document.createElement("img");im.loading="lazy";im.alt="";im.src=p.t;
  b.appendChild(im);b.onclick=()=>openLb(i);grid.appendChild(b);
});
let cur=0;
function showLb(){$("lbImg").src=D.photos[cur].f;$("lbCnt").textContent=(cur+1)+" / "+D.photos.length}
function openLb(i){cur=i;showLb();$("lb").classList.add("open")}
function closeLb(){$("lb").classList.remove("open");$("lbImg").removeAttribute("src")}
function step(d){cur=(cur+d+D.photos.length)%D.photos.length;showLb()}
$("lbX").onclick=closeLb;$("lbP").onclick=()=>step(-1);$("lbN").onclick=()=>step(1);
$("stage").addEventListener("click",e=>{if(e.target===$("stage")||e.target===$("lbImg"))closeLb()});
let sx=null;
$("stage").addEventListener("touchstart",e=>{sx=e.touches[0].clientX},{passive:true});
$("stage").addEventListener("touchend",e=>{
  if(sx===null)return;const dx=e.changedTouches[0].clientX-sx;sx=null;
  if(Math.abs(dx)>50)step(dx<0?1:-1);
},{passive:true});

/* отзывы */
function stars(n){
  const s=document.createElement("span");s.className="stars";s.setAttribute("aria-label","Оценка "+n+" из 5");
  s.appendChild(document.createTextNode("★".repeat(n)));
  if(n<5){const i=document.createElement("i");i.textContent="★".repeat(5-n);s.appendChild(i)}
  return s;
}
(function(){
  const list=$("rvList");
  if(!D.reviews.length){$("rvEmpty").hidden=false}
  D.reviews.forEach(r=>{
    const c=document.createElement("div");c.className="rv";
    c.appendChild(stars(Math.max(1,Math.min(5,Number(r.r)||5))));
    const p=document.createElement("p");p.textContent=r.t;c.appendChild(p);
    const w=document.createElement("div");w.className="who";
    const b=document.createElement("b");b.textContent=r.a||"Клиент";
    const d=document.createElement("span");d.textContent=r.d||"";
    w.appendChild(b);w.appendChild(d);c.appendChild(w);list.appendChild(c);
  });
  if(D.reviews.length){
    const avg=D.reviews.reduce((s,r)=>s+(Number(r.r)||5),0)/D.reviews.length;
    const a=$("avg");const b=document.createElement("b");b.textContent=avg.toFixed(1).replace(".",",");
    a.appendChild(b);const t=document.createElement("div");
    t.appendChild(stars(Math.round(avg)));
    const n=document.createElement("div");n.textContent="отзывов: "+D.reviews.length;t.appendChild(n);a.appendChild(t);
  }
})();

/* форма отзыва (нужен Worker и ссылка из галереи клиента) */
let rating=5;
const canReview=!!(D.worker&&G);
$("addRev").hidden=!canReview;
(function(){
  const pick=$("pick");
  for(let i=1;i<=5;i++){
    const b=document.createElement("button");b.type="button";b.textContent="★";b.setAttribute("aria-label",i+" из 5");
    b.onclick=()=>{rating=i;paint()};pick.appendChild(b);
  }
  function paint(){[...pick.children].forEach((b,k)=>b.classList.toggle("on",k<rating))}
  paint();window.paintPick=paint;
})();
function openDlg(){
  const sent=store.get("rv_"+G)==="1";
  $("dForm").hidden=sent;$("dDone").hidden=!sent;
  $("rvErr").textContent="";$("dlg").classList.add("open");
  if(!sent)setTimeout(()=>$("rvName").focus(),50);
}
function closeDlg(){$("dlg").classList.remove("open")}
$("addRev").onclick=openDlg;$("dX").onclick=closeDlg;$("dOk").onclick=closeDlg;
$("dlg").addEventListener("mousedown",e=>{if(e.target===$("dlg"))closeDlg()});
$("rvSend").onclick=async()=>{
  const name=$("rvName").value.trim(),text=$("rvText").value.trim(),err=$("rvErr");
  if(text.length<10){err.textContent="Напишите хотя бы пару предложений.";return}
  const btn=$("rvSend");btn.disabled=true;btn.textContent="Отправляю…";err.textContent="";
  try{
    const r=await fetch(D.worker+"/review",{method:"POST",headers:{"Content-Type":"text/plain;charset=UTF-8"},
      body:JSON.stringify({slug:G,author:name,text:text,rating:rating})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok||!j.ok){
      err.textContent=j.error==="limit"?"Вы уже отправили несколько отзывов. Спасибо!":
        j.error==="unknown gallery"?"Эта ссылка больше не действует.":"Не получилось отправить. Попробуйте ещё раз.";
    }else{
      store.set("rv_"+G,"1");$("dForm").hidden=true;$("dDone").hidden=false;
    }
  }catch(e){err.textContent="Нет связи. Проверьте интернет и повторите."}
  btn.disabled=false;btn.textContent="Отправить отзыв";
};
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){if($("dlg").classList.contains("open"))closeDlg();else if($("lb").classList.contains("open"))closeLb()}
  else if($("lb").classList.contains("open")){if(e.key==="ArrowLeft")step(-1);else if(e.key==="ArrowRight")step(1)}
});
if(location.hash==="#reviews")tab("rev");
</script></body></html>
"""

TEMPLATE = r"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#3E2C23">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&family=Playfair+Display:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#3E2C23;--side:#33241C;--card:#5B4133;--field:#4A362B;--border:#6B4F3F;--second:#87634F;
  --text:#EFE3D8;--beige:#D9C3B1;--muted:#B9A08F;--light:#E6F4FB;
  --blue:#A7D8F0;--blue-h:#75C0E6;--on-blue:#2B1D16;
  --body:Montserrat,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --head:"Playfair Display",Georgia,"Times New Roman",serif;
  --safe:env(safe-area-inset-bottom,0px);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
[hidden]{display:none!important}
html{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--body);font-size:15px;line-height:1.4;
  padding-bottom:calc(92px + var(--safe))}
button,input,textarea{font-family:inherit}
button{cursor:pointer;border:0}

/* шапка */
.hero{padding:28px 20px 14px;max-width:1500px;margin:0 auto}
.hero h1{font-family:var(--head);font-weight:500;font-size:clamp(26px,4.6vw,44px);line-height:1.15;margin:0 0 8px;color:var(--light)}
.hero p{margin:0;color:var(--muted);font-size:14px;max-width:640px}

/* панель инструментов */
.tools{position:sticky;top:0;z-index:5;background:rgba(62,44,35,.92);backdrop-filter:blur(10px);
  -webkit-backdrop-filter:blur(10px);border-bottom:1px solid rgba(107,79,63,.6)}
.tools-in{max-width:1500px;margin:0 auto;padding:10px 20px;display:flex;gap:10px 14px;align-items:center;flex-wrap:wrap}
.all{display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none;font-weight:500;padding:6px 4px}
.all input{position:absolute;opacity:0;width:0;height:0}
.box-i{width:24px;height:24px;border-radius:7px;border:2px solid var(--second);background:var(--field);
  display:flex;align-items:center;justify-content:center;transition:.15s;flex:none}
.box-i svg{width:15px;height:15px;stroke:var(--on-blue);stroke-width:3.2;fill:none;stroke-linecap:round;stroke-linejoin:round;opacity:0}
.all input:checked+.box-i,.all input:indeterminate+.box-i{background:var(--blue);border-color:var(--blue)}
.all input:checked+.box-i svg.ck,.all input:indeterminate+.box-i svg.mi{opacity:1}
.all input:indeterminate+.box-i svg.ck{display:none}
.all input:not(:indeterminate)+.box-i svg.mi{display:none}
.all input:focus-visible+.box-i{outline:2px solid var(--blue-h);outline-offset:2px}
.btn{border-radius:12px;padding:10px 16px;font-size:14px;font-weight:600;transition:.15s;display:inline-flex;
  align-items:center;gap:8px;text-decoration:none;white-space:nowrap}
.btn.primary{background:var(--blue);color:var(--on-blue)}
.btn.primary:hover{background:var(--blue-h)}
.btn.ghost{background:var(--card);color:var(--text)}
.btn.ghost:hover{background:#6E5141}
.btn.line{background:transparent;color:var(--text);border:1px solid var(--border)}
.btn.line:hover{background:rgba(255,255,255,.06)}
.btn:disabled{opacity:.5;cursor:default}
.seg{display:flex;background:var(--field);border-radius:12px;padding:3px;margin-left:auto}
.seg button{background:transparent;color:var(--muted);padding:7px 14px;border-radius:9px;font-size:13px;font-weight:600}
.seg button.on{background:var(--card);color:var(--light)}
.count{font-size:14px;color:var(--beige);white-space:nowrap}
.count b{font-size:18px;color:var(--light)}

/* сетка */
.wrap{max-width:1500px;margin:0 auto;padding:16px 14px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;align-items:start}
.item{background:var(--card);border-radius:16px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.18);transition:box-shadow .15s}
.item.sel{box-shadow:0 0 0 3px var(--blue),0 6px 18px rgba(0,0,0,.28)}
.photo{position:relative;aspect-ratio:1;overflow:hidden;cursor:zoom-in;background:#2c1f18}
.photo img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .35s}
@media (hover:hover){.photo:hover img{transform:scale(1.04)}}
.chk{position:absolute;top:10px;left:10px;width:42px;height:42px;border-radius:50%;
  background:rgba(43,29,22,.55);border:2px solid rgba(255,255,255,.85);display:flex;align-items:center;
  justify-content:center;cursor:pointer;transition:.15s;backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
.chk svg{width:22px;height:22px;stroke:#fff;stroke-width:3.2;fill:none;stroke-linecap:round;stroke-linejoin:round;opacity:0}
.item.sel .chk{background:var(--blue);border-color:var(--blue)}
.item.sel .chk svg{opacity:1;stroke:var(--on-blue)}
.nm{position:absolute;left:0;bottom:0;right:0;padding:18px 10px 7px;font-size:11px;color:#fff;
  background:linear-gradient(transparent,rgba(0,0,0,.6));white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row{display:flex;gap:6px;padding:8px;align-items:center}
.row input{flex:1;min-width:0;padding:9px 11px;border-radius:10px;border:1px solid transparent;background:var(--field);
  color:var(--text);font-size:13px}
.row input::placeholder{color:var(--muted)}
.row{flex-wrap:wrap}
.row .cinp{flex:1 1 100%;order:3}
.svc{flex:1;min-width:0;appearance:none;-webkit-appearance:none;border:1px solid transparent;border-radius:10px;
  padding:10px 30px 10px 11px;background-color:var(--field);color:var(--text);font-size:13px;font-weight:500;cursor:pointer;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'><path d='M1 1l5 5 5-5' fill='none' stroke='%23D9C3B1' stroke-width='2' stroke-linecap='round'/></svg>");
  background-repeat:no-repeat;background-position:right 11px center;text-overflow:ellipsis}
.svc:focus{outline:none;border-color:var(--blue)}
.svc option{background:#4A362B;color:#EFE3D8}
.prices{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.pr{background:var(--card);border-radius:12px;padding:8px 14px;font-size:13px;color:var(--beige)}
.pr b{color:var(--light);font-weight:600;margin-right:6px}
.pr.disc{background:rgba(167,216,240,.14);color:var(--blue)}
.pr.disc b{color:var(--blue)}
.dlg-sum .ln{display:flex;justify-content:space-between;gap:12px}
.dlg-sum .tot{border-top:1px solid var(--border);margin-top:6px;padding-top:6px;font-size:16px;color:var(--light)}
.dlg-sum .hint{color:var(--blue);font-size:12px;margin-top:6px}
.lb-bot-in{width:100%;max-width:620px;display:flex;gap:8px;flex-wrap:wrap}
.lb-bot-in .svc{flex:0 0 auto;min-width:190px;padding:13px 32px 13px 14px;font-size:15px;border-color:var(--border)}
.lb-bot-in input{flex:1;min-width:160px}
.row input:focus{outline:none;border-color:var(--blue)}
.ibtn{width:38px;height:38px;border-radius:10px;background:var(--field);color:var(--beige);display:flex;
  align-items:center;justify-content:center;text-decoration:none;flex:none;transition:.15s}
.ibtn:hover{background:#6E5141;color:var(--light)}
.ibtn svg{width:18px;height:18px;stroke:currentColor;stroke-width:2;fill:none;stroke-linecap:round;stroke-linejoin:round}
.empty{text-align:center;color:var(--muted);padding:60px 20px}

/* нижняя панель */
.bar{position:fixed;left:0;right:0;bottom:0;z-index:6;background:rgba(51,36,28,.94);backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);border-top:1px solid var(--border);padding:12px 20px calc(12px + var(--safe))}
.bar-in{max-width:1500px;margin:0 auto;display:flex;gap:14px;align-items:center;justify-content:space-between}
.sum{min-width:0}
.sum .big{font-size:16px;font-weight:600;color:var(--light)}
.chip{display:inline-block;font-size:12px;margin-top:2px;color:var(--muted)}
.chip.ok{color:var(--blue)}
.bar .btn.primary{padding:14px 26px;font-size:15px;border-radius:14px}

/* просмотр */
#lb{position:fixed;inset:0;z-index:20;background:#1c130e;display:none;flex-direction:column}
#lb.open{display:flex}
.lb-top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;flex:none}
.lb-top .cnt2{color:var(--beige);font-size:14px;min-width:64px}
.lb-act{display:flex;gap:8px;align-items:center}
.stage{flex:1;min-height:0;position:relative;display:flex;align-items:center;justify-content:center;touch-action:pan-y}
.stage img{max-width:100%;max-height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none}
.nav{position:absolute;top:50%;transform:translateY(-50%);width:48px;height:64px;border-radius:14px;
  background:rgba(91,65,51,.7);color:var(--light);font-size:30px;display:flex;align-items:center;justify-content:center}
.nav:hover{background:var(--card)}
.nav.prev{left:10px}.nav.next{right:10px}
.lb-bot{padding:10px 14px calc(14px + var(--safe));flex:none;display:flex;justify-content:center}
.lb-bot input{width:100%;max-width:620px;padding:13px 14px;border-radius:12px;border:1px solid var(--border);
  background:var(--field);color:var(--text);font-size:15px}
.lb-bot input:focus{outline:none;border-color:var(--blue)}
@media (max-width:640px){.nav{display:none}}

/* диалог */
#dlg{position:fixed;inset:0;z-index:30;background:rgba(20,13,9,.72);display:none;align-items:center;
  justify-content:center;padding:16px;backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px)}
#dlg.open{display:flex}
.dlg-box{position:relative;background:var(--bg);border:1px solid var(--border);border-radius:22px;padding:26px 22px 22px;
  width:100%;max-width:440px;max-height:92vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.dlg-x{position:absolute;top:12px;right:12px;width:38px;height:38px;border-radius:50%;background:var(--card);color:var(--beige);font-size:18px}
.dlg-x:hover{background:#6E5141}
.dlg-box h2{font-family:var(--head);font-weight:500;font-size:26px;margin:0 36px 6px 0;color:var(--light)}
.dlg-box p{margin:0 0 14px;color:var(--beige);font-size:14px}
.dlg-box label{display:block;font-size:13px;color:var(--muted);margin:12px 0 6px}
.dlg-box input,.dlg-box textarea{width:100%;padding:13px 14px;border-radius:12px;border:1px solid var(--border);
  background:var(--field);color:var(--text);font-size:16px;resize:vertical}
.dlg-box input:focus,.dlg-box textarea:focus{outline:none;border-color:var(--blue)}
.dlg-sum{margin:14px 0 4px;padding:12px 14px;border-radius:12px;background:var(--card);color:var(--beige);font-size:14px}
.dlg-sum b{color:var(--light)}
.dlg-btns{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap}
.dlg-btns .btn{flex:1;justify-content:center;padding:13px 16px}
.okmark{width:64px;height:64px;border-radius:50%;background:var(--blue);display:flex;align-items:center;
  justify-content:center;margin:2px 0 14px}
.okmark svg{width:34px;height:34px;stroke:var(--on-blue);stroke-width:3.4;fill:none;stroke-linecap:round;stroke-linejoin:round}
.err{color:#ffb4a8}

/* уведомление */
#toast{position:fixed;left:50%;bottom:calc(96px + var(--safe));transform:translate(-50%,20px);z-index:40;opacity:0;
  pointer-events:none;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:14px;
  padding:12px 16px;display:flex;gap:14px;align-items:center;box-shadow:0 10px 30px rgba(0,0,0,.4);
  max-width:min(92vw,460px);font-size:14px;transition:.22s;white-space:nowrap}
#toast.show{opacity:1;transform:translate(-50%,0);pointer-events:auto}
#toast button{background:transparent;color:var(--blue);font-weight:600;font-size:14px;padding:4px 6px}

@media (max-width:640px){
  .hero{padding:20px 16px 10px}
  .tools{position:static}
  .count{display:none}
  .tools-in{padding:8px 12px;gap:8px 10px}
  .seg{margin-left:0;order:3;width:100%}.seg button{flex:1}
  .wrap{padding:12px 8px 0}
  .grid{grid-template-columns:repeat(2,1fr);gap:8px}
  .item{border-radius:14px}
  .chk{width:44px;height:44px;top:8px;left:8px}
  .row{padding:6px}
  .row input{padding:8px 9px;font-size:12px}
  .svc{font-size:12px;padding:9px 26px 9px 9px;background-position:right 9px center}
  .lb-bot-in .svc{flex:1 1 100%}
  .bar{padding:10px 12px calc(10px + var(--safe))}
  .bar .btn.primary{padding:14px 20px}
}
@media (min-width:1200px){.grid{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
</style></head><body>

<header class="hero">
  <h1>__TITLE__</h1>
  <p>Нажмите на фото, чтобы рассмотреть его. Кружок в углу отмечает фото. Под каждым фото выберите, что с ним сделать: цветокоррекция (по умолчанию), ретушь или комментарий.</p>
  <div class="prices" id="prices"></div>
  <a class="btn line" id="pfBtn" hidden style="margin-top:14px" href="../_portfolio/index.html?g=__SLUG__">Портфолио и отзывы</a>
  <script>if(__PORTFOLIO__)document.getElementById("pfBtn").hidden=false;</script>
</header>

<div class="tools"><div class="tools-in">
  <label class="all"><input type="checkbox" id="allChk"><span class="box-i">
    <svg class="ck" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>
    <svg class="mi" viewBox="0 0 24 24"><path d="M6 12h12"/></svg></span><span>Выбрать все</span></label>
  <button class="btn line" id="clearBtn" type="button">Снять все</button>
  <div class="count"><b id="cnt">0</b><span id="lim"></span></div>
  <div class="seg" role="tablist">
    <button type="button" data-f="all" class="on">Все фото</button>
    <button type="button" data-f="sel">Только выбранные</button>
  </div>
</div></div>

<main class="wrap">
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" hidden>Пока ничего не выбрано.<br>Отметьте фото кружком в углу.</div>
</main>

<div class="bar"><div class="bar-in">
  <div class="sum"><div class="big" id="sumTxt">Выбрано: 0</div><span class="chip" id="chip"></span></div>
  <button class="btn primary" id="sendBtn" type="button">Отправить выбор</button>
</div></div>

<div id="lb" role="dialog" aria-modal="true" aria-label="Просмотр фото">
  <div class="lb-top">
    <span class="cnt2" id="lbCount"></span>
    <div class="lb-act">
      <button class="btn primary" id="lbSel" type="button">Выбрать</button>
      <a class="ibtn" id="lbDl" href="#" download title="Скачать" aria-label="Скачать"><svg viewBox="0 0 24 24"><path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg></a>
      <button class="ibtn" id="lbClose" type="button" aria-label="Закрыть"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    </div>
  </div>
  <div class="stage" id="stage">
    <button class="nav prev" id="lbPrev" type="button" aria-label="Назад">‹</button>
    <img id="lbImg" alt="">
    <button class="nav next" id="lbNext" type="button" aria-label="Вперёд">›</button>
  </div>
  <div class="lb-bot"><div class="lb-bot-in"><select class="svc" id="lbSvc" aria-label="Что сделать с фото"></select>
    <input id="lbCom" maxlength="300" placeholder="Комментарий к этому фото" hidden></div></div>
</div>

<div id="dlg"><div class="dlg-box" id="dlgBox"></div></div>
<div id="toast"><span id="toastTxt"></span><button id="toastBtn" type="button" hidden></button></div>

<script>
const PHOTOS=__PHOTOS__;
const TG_TOKEN=__TG_TOKEN__, TG_CHAT=__TG_CHAT__, WORKER=__WORKER__, SLUG="__SLUG__", MAX=__MAX__, LS="sel_"+location.pathname, LC="com_"+location.pathname, LN="nm_"+location.pathname, LG="gc_"+location.pathname, LSENT="sent_"+location.pathname;
const PRICING=__PRICING__;
const GALLERY="__GALLERY__", PRICES=__PRICES__, LV="svc_"+location.pathname;
const SVC=[["color","Цветокоррекция"],["retouch","Ретушь"],["comment","Комментарий"]];
const SVCN=Object.fromEntries(SVC);
let svc={};
let sel=new Set(), com={}, cur=0, filter="all", lastSent="";
const $=id=>document.getElementById(id);
const store={
  get(k){try{return localStorage.getItem(k)}catch(e){return null}},
  set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
};
try{sel=new Set(JSON.parse(store.get(LS)||"[]"))}catch(e){}
try{const c=JSON.parse(store.get(LC)||"{}");if(c&&typeof c==="object")com=c}catch(e){}
try{const v=JSON.parse(store.get(LV)||"{}");if(v&&typeof v==="object")for(const n in v)if(SVCN[v[n]]&&v[n]!=="color")svc[n]=v[n]}catch(e){}
lastSent=store.get(LSENT)||"";
{const known=new Set(PHOTOS.map(p=>p.n));sel=new Set([...sel].filter(n=>known.has(n)))}   // фото могли убрать из галереи
const fileName=p=>{try{return decodeURIComponent(p.f.split("/").pop())}catch(e){return p.f.split("/").pop()}};
const ICON_CHK='<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
const ICON_DL='<svg viewBox="0 0 24 24"><path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19h14"/></svg>';

function save(){store.set(LS,JSON.stringify([...sel]));store.set(LC,JSON.stringify(com));store.set(LV,JSON.stringify(svc))}
const svcOf=n=>svc[n]||"color";
const hasCom=n=>svcOf(n)==="comment"&&!!com[n]&&!!com[n].trim();
function signature(){
  const names=PHOTOS.map(p=>p.n).filter(n=>sel.has(n));
  return JSON.stringify(names.map(n=>[n,svcOf(n),hasCom(n)?com[n]:""]));
}
function comCount(){return PHOTOS.filter(p=>sel.has(p.n)&&hasCom(p.n)).length}
function svcCounts(){const c={color:0,retouch:0,comment:0};PHOTOS.forEach(p=>{if(sel.has(p.n))c[svcOf(p.n)]++});return c}
function svcLabel(k){return SVCN[k]}
const hasPrice=SVC.some(([k])=>(PRICING.num[k]||0)>0);
const money=v=>{v=Math.round(v*100)/100;return v.toLocaleString("ru-RU",{minimumFractionDigits:v%1?2:0,maximumFractionDigits:2})+(PRICING.cur?" "+PRICING.cur:"")};
function calc(){
  const c=svcCounts();let sub=0,paid=0;
  for(const [k] of SVC){const pr=PRICING.num[k]||0;sub+=c[k]*pr;if(pr>0)paid+=c[k]}
  let pct=0,next=null;
  for(const [n,p] of PRICING.tiers){if(paid>=n)pct=p;else if(!next)next=[n,p]}
  const disc=Math.floor(sub*pct+0.5)/100;
  return {c,sub,paid,pct,disc,total:sub-disc,next};
}
function fillSelect(s){SVC.forEach(([k])=>{const o=document.createElement("option");o.value=k;o.textContent=svcLabel(k);s.appendChild(o)})}
(function(){
  const box=$("prices");
  SVC.forEach(([k,t])=>{
    if(!PRICES[k])return;
    const d=document.createElement("span");d.className="pr";
    const b=document.createElement("b");b.textContent=t;
    d.appendChild(b);d.appendChild(document.createTextNode(PRICES[k]));box.appendChild(d);
  });
  if(PRICING.tiers.length&&hasPrice){
    const d=document.createElement("span");d.className="pr disc";
    const b=document.createElement("b");b.textContent="Скидка";
    d.appendChild(b);d.appendChild(document.createTextNode(PRICING.tiers.map(t=>"от "+t[0]+" фото −"+t[1]+"%").join(", ")));
    box.appendChild(d);
  }
  box.hidden=!box.children.length;
})();

/* уведомление с отменой */
let toastTimer=0;
function toast(msg,action){
  $("toastTxt").textContent=msg;
  const b=$("toastBtn");
  if(action){b.hidden=false;b.textContent=action.label||"Отменить";b.onclick=()=>{action.fn();hideToast()}}
  else{b.hidden=true;b.onclick=null}
  $("toast").classList.add("show");
  clearTimeout(toastTimer);toastTimer=setTimeout(hideToast,action?6500:3200);
}
function hideToast(){$("toast").classList.remove("show")}

/* выбор */
const els=[];
function setCom(i,v){
  const n=PHOTOS[i].n;
  if(v.trim())com[n]=v;else delete com[n];
  save();renderMeta();
}
function setSvc(i,k){
  const n=PHOTOS[i].n;
  if(k==="color")delete svc[n];else svc[n]=k;
  if(!sel.has(n)&&!(MAX&&sel.size>=MAX))sel.add(n);    // выбрал услугу: значит, фото нужно
  save();render();
}
function syncSvc(i){
  const n=PHOTOS[i].n,k=svcOf(n),e=els[i];
  e.sel.value=k;e.inp.hidden=k!=="comment";
  if($("lb").classList.contains("open")&&cur===i){$("lbSvc").value=k;$("lbCom").hidden=k!=="comment"}
}
function toggle(i){
  const n=PHOTOS[i].n;
  if(sel.has(n))sel.delete(n);
  else{
    if(MAX&&sel.size>=MAX){toast("Можно выбрать не больше "+MAX+" фото");return}
    sel.add(n);
  }
  save();render();
}
function selectAll(){
  let limit=false;
  for(const p of PHOTOS){
    if(sel.has(p.n))continue;
    if(MAX&&sel.size>=MAX){limit=true;break}
    sel.add(p.n);
  }
  save();render();
  if(limit)toast("Выбрано максимум: "+MAX+" фото");
}
function clearAll(){
  if(!sel.size)return;
  const prev=new Set(sel);
  sel.clear();save();render();
  toast("Выбор снят",{label:"Отменить",fn:()=>{prev.forEach(n=>sel.add(n));save();render()}});
}
function renderMeta(){
  const n=sel.size, c=comCount();
  $("cnt").textContent=n;
  $("lim").textContent=MAX?(" из "+MAX):" выбрано";
  $("sumTxt").textContent="Выбрано: "+n+(MAX?" из "+MAX:"")+(hasPrice&&n?" · "+money(calc().total):"");
  const chip=$("chip");
  if(!lastSent){chip.textContent=c?("Комментариев: "+c):"";chip.className="chip"}
  else if(lastSent===signature()){chip.textContent="✓ Выбор отправлен";chip.className="chip ok"}
  else{chip.textContent="Есть изменения после отправки"+(c?" · комментариев: "+c:"");chip.className="chip"}
  const all=$("allChk"), full=PHOTOS.length&&n>=Math.min(PHOTOS.length,MAX||PHOTOS.length);
  all.checked=!!(n&&full);
  all.indeterminate=!!(n&&!full);
}
function render(){
  renderMeta();
  els.forEach((e,i)=>{
    syncSvc(i);
    const on=sel.has(PHOTOS[i].n);
    e.item.classList.toggle("sel",on);
    e.chk.setAttribute("aria-pressed",on);
    e.item.hidden=(filter==="sel"&&!on);
  });
  $("empty").hidden=!(filter==="sel"&&!sel.size);
  if($("lb").classList.contains("open"))lbRefresh();
}

/* сетка */
const grid=$("grid");
PHOTOS.forEach((p,i)=>{
  const item=document.createElement("div");item.className="item";
  const ph=document.createElement("div");ph.className="photo";
  ph.innerHTML='<img loading="lazy" decoding="async" alt=""><button class="chk" type="button" aria-label="Выбрать фото">'+ICON_CHK+'</button><div class="nm"></div>';
  ph.querySelector("img").src=p.t;
  ph.querySelector(".nm").textContent=p.n;
  const chk=ph.querySelector(".chk");
  chk.onclick=e=>{e.stopPropagation();toggle(i)};
  ph.onclick=()=>openLb(i);
  const row=document.createElement("div");row.className="row";
  const sl=document.createElement("select");sl.className="svc";sl.setAttribute("aria-label","Что сделать с фото");fillSelect(sl);
  sl.value=svcOf(p.n);
  const inp=document.createElement("input");
  inp.className="cinp";inp.maxLength=300;inp.placeholder="Комментарий к фото";inp.value=com[p.n]||"";inp.hidden=svcOf(p.n)!=="comment";
  sl.onchange=()=>{setSvc(i,sl.value);if(sl.value==="comment")inp.focus()};
  inp.oninput=()=>{setCom(i,inp.value);if($("lb").classList.contains("open")&&cur===i)$("lbCom").value=inp.value};
  const a=document.createElement("a");a.className="ibtn";a.innerHTML=ICON_DL;
  a.href=p.f;a.download=fileName(p);a.title="Скачать фото";a.setAttribute("aria-label","Скачать фото");
  row.appendChild(sl);row.appendChild(a);row.appendChild(inp);
  item.appendChild(ph);item.appendChild(row);
  grid.appendChild(item);
  els.push({item,chk,inp,sel:sl});
});

/* верхняя панель */
$("allChk").addEventListener("change",e=>{if(e.target.checked)selectAll();else clearAll()});
$("clearBtn").onclick=clearAll;
document.querySelectorAll(".seg button").forEach(b=>b.onclick=()=>{
  filter=b.dataset.f;
  document.querySelectorAll(".seg button").forEach(x=>x.classList.toggle("on",x===b));
  render();window.scrollTo({top:0});
});

/* просмотр фото */
let lockCount=0;
function lock(on){lockCount+=on?1:-1;document.body.style.overflow=lockCount>0?"hidden":""}
function lbRefresh(){
  const p=PHOTOS[cur], on=sel.has(p.n);
  $("lbSel").textContent=on?"✓ Выбрано":"Выбрать";
  $("lbSel").className="btn "+(on?"ghost":"primary");
  $("lbCount").textContent=(cur+1)+" / "+PHOTOS.length;
}
function showLb(){
  const p=PHOTOS[cur];
  $("lbImg").src=p.f;
  $("lbCom").value=com[p.n]||"";
  $("lbSvc").value=svcOf(p.n);$("lbCom").hidden=svcOf(p.n)!=="comment";
  $("lbDl").href=p.f;$("lbDl").download=fileName(p);
  lbRefresh();
  for(const d of [1,-1]){const q=PHOTOS[(cur+d+PHOTOS.length)%PHOTOS.length];if(q){const im=new Image();im.src=q.f}}
}
function openLb(i){hideToast();cur=i;if(!$("lb").classList.contains("open")){$("lb").classList.add("open");lock(true)}showLb()}
function closeLb(){
  if(!$("lb").classList.contains("open"))return;
  $("lb").classList.remove("open");$("lbImg").src="";lock(false);
  if(document.activeElement)document.activeElement.blur();
}
function step(d){cur=(cur+d+PHOTOS.length)%PHOTOS.length;showLb()}
$("lbClose").onclick=closeLb;
$("lbPrev").onclick=()=>step(-1);
$("lbNext").onclick=()=>step(1);
$("lbSel").onclick=()=>toggle(cur);
fillSelect($("lbSvc"));
$("lbSvc").onchange=()=>{setSvc(cur,$("lbSvc").value);if($("lbSvc").value==="comment")$("lbCom").focus()};
$("lbCom").oninput=()=>{setCom(cur,$("lbCom").value);els[cur].inp.value=$("lbCom").value};
{
  let x0=0,y0=0,t0=0;
  const st=$("stage");
  st.addEventListener("touchstart",e=>{if(e.touches.length!==1)return;x0=e.touches[0].clientX;y0=e.touches[0].clientY;t0=Date.now()},{passive:true});
  st.addEventListener("touchend",e=>{
    if(!e.changedTouches.length||!t0)return;
    const dx=e.changedTouches[0].clientX-x0, dy=e.changedTouches[0].clientY-y0, dt=Date.now()-t0;t0=0;
    if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.5&&dt<700)step(dx<0?1:-1);
  },{passive:true});
  st.addEventListener("click",e=>{if(e.target===st)closeLb()});
}

/* диалоги */
function openDlg(html){
  hideToast();
  $("dlgBox").innerHTML='<button class="dlg-x" type="button" aria-label="Закрыть" id="dlgX">✕</button>'+html;
  if(!$("dlg").classList.contains("open")){$("dlg").classList.add("open");lock(true)}
  $("dlgX").onclick=closeDlg;
}
function closeDlg(){
  if(!$("dlg").classList.contains("open"))return;
  $("dlg").classList.remove("open");lock(false);
}
$("dlg").addEventListener("mousedown",e=>{if(e.target===$("dlg"))closeDlg()});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function openForm(){
  if(!sel.size){toast("Сначала отметьте фото кружком в углу");return}
  openDlg('<h2>Отправить выбор</h2><p>Фотограф получит список отмеченных фото, выбранные услуги и комментарии.</p>'+
    '<label for="fName">Ваше имя *</label><input id="fName" autocomplete="name" maxlength="80">'+
    '<label for="fComment">Общий комментарий (необязательно)</label><textarea id="fComment" rows="3" maxlength="1000"></textarea>'+
    '<div class="dlg-sum">'+sumHtml()+'</div>'+
    '<div class="dlg-btns"><button class="btn primary" id="goBtn" type="button">Отправить</button>'+
    '<button class="btn ghost" id="cancelBtn" type="button">Вернуться к выбору</button></div>');
  $("fName").value=store.get(LN)||"";
  $("fComment").value=store.get(LG)||"";
  $("goBtn").onclick=send;
  $("cancelBtn").onclick=closeDlg;
  $("fName").addEventListener("keydown",e=>{if(e.key==="Enter")send()});
  if(!$("fName").value)setTimeout(()=>$("fName").focus(),60);
}
function sumHtml(){
  const r=calc();let h='<div class="ln"><span>Выбрано фото</span><b>'+sel.size+'</b></div>';
  for(const [k,t] of SVC){
    if(!r.c[k])continue;const pr=PRICING.num[k]||0;
    h+='<div class="ln"><span>'+esc(t)+(hasPrice?" · "+r.c[k]+" × "+money(pr):"")+'</span><b>'+(hasPrice?money(r.c[k]*pr):r.c[k])+'</b></div>';
  }
  if(hasPrice){
    if(r.pct)h+='<div class="ln"><span>Сумма</span><b>'+money(r.sub)+'</b></div><div class="ln"><span>Скидка '+r.pct+'%</span><b>−'+money(r.disc)+'</b></div>';
    h+='<div class="ln tot"><span>Итого</span><b>'+money(r.total)+'</b></div>';
    if(r.next){const m=r.next[0]-r.paid;h+='<div class="hint">Ещё '+m+' фото — и скидка станет '+r.next[1]+'%</div>'}
  }
  return h;
}
function showSuccess(n){
  openDlg('<div class="okmark"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>'+
    '<h2>Фото отправлено</h2><p>Фотограф получил ваш выбор: '+n+' фото. Спасибо!</p>'+
    '<p style="color:var(--muted);font-size:13px">Это окно можно закрыть и продолжить выбирать. Если что-то измените, нажмите «Отправить выбор» ещё раз.</p>'+
    '<div class="dlg-btns"><button class="btn primary" id="contBtn" type="button">Продолжить выбор</button></div>');
  $("contBtn").onclick=closeDlg;
  $("contBtn").focus();
}
function showFileSaved(){
  openDlg('<h2>Файл со списком скачан</h2><p>Отправьте этот файл фотографу, например в мессенджере. Выбор сохранён на этой странице, можно продолжать.</p>'+
    '<div class="dlg-btns"><button class="btn primary" id="contBtn" type="button">Продолжить выбор</button></div>');
  $("contBtn").onclick=closeDlg;
}
function showError(msg,text,fileLabel){
  openDlg('<h2>Не удалось отправить</h2><p class="err">'+esc(msg)+'</p>'+
    '<p>Выбор сохранён на странице. Попробуйте ещё раз или скачайте список файлом и перешлите его фотографу.</p>'+
    '<div class="dlg-btns"><button class="btn primary" id="retryBtn" type="button">Повторить</button>'+
    '<button class="btn ghost" id="fileBtn" type="button">Скачать файлом</button></div>');
  $("retryBtn").onclick=openForm;
  $("fileBtn").onclick=()=>{download(fileLabel,text);toast("Файл скачан")};
}

/* отправка: формат текста разбирает приложение фотографа, не менять */
function clean(s){
  return String(s).replace(/\s+/g," ").replace(/\|/g,"/")
    .replace(/(Файлы|Комментарии к фото|Услуги по фото|Итого)\s*:/gi,"$1 -").trim();
}
function download(name,text){
  const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));
  const a=document.createElement("a");
  a.href=url;a.download=name;a.style.display="none";
  document.body.appendChild(a);a.click();
  setTimeout(()=>{a.remove();URL.revokeObjectURL(url)},1000);
}
function chunks(text,max){
  const out=[];let cur="";
  for(const line of text.split("\n")){
    if(cur&&(cur.length+line.length+1)>max){out.push(cur);cur=""}
    cur+=(cur?"\n":"")+line;
  }
  if(cur)out.push(cur);
  return out;
}
async function viaTelegram(text){
  const url="https://api.telegram.org/bot"+TG_TOKEN+"/sendMessage";
  for(const part of chunks(text,3800)){
    const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({chat_id:TG_CHAT,text:part,disable_web_page_preview:true})});
    const j=await r.json();
    if(!j.ok)throw new Error("Telegram: "+(j.description||r.status));
  }
}
async function viaWorker(text,name,count){
  const r=await fetch(WORKER+"/sel",{method:"POST",headers:{"Content-Type":"text/plain;charset=UTF-8"},
    body:JSON.stringify({slug:SLUG,gallery:GALLERY,client:name,count:count,text:text})});
  let j={};try{j=await r.json()}catch(e){}
  if(!r.ok||!j.ok)throw new Error("сервер: "+(j.error||r.status));
}
let sending=false;
async function send(){
  if(sending)return;
  const rawName=$("fName").value;
  const name=clean(rawName);
  if(!name){toast("Введите ваше имя");$("fName").focus();return}
  const list=PHOTOS.map(p=>p.n).filter(n=>sel.has(n));
  if(!list.length){closeDlg();toast("Сначала отметьте фото");return}
  store.set(LN,rawName.trim());store.set(LG,$("fComment").value);
  const comLines=list.filter(n=>hasCom(n)&&clean(com[n])).map(n=>n+" | "+clean(com[n]));
  const svcLines=list.map(n=>n+" | "+SVCN[svcOf(n)]);
  const r=calc();
  const money_line=hasPrice?("\nИтого: "+String(Math.round(r.total*100)/100)+(PRICING.cur?" "+PRICING.cur:"")+(r.pct?" (сумма "+Math.round(r.sub*100)/100+", скидка "+r.pct+"%)":"")):"";
  let text="Галерея: "+GALLERY+"\nКлиент: "+name+"\nВыбрано: "+list.length+money_line+"\nКомментарий: "+(clean($("fComment").value)||"-")+
    "\n\nФайлы:\n"+list.join("\n");
  text+="\n\nУслуги по фото:\n"+svcLines.join("\n");
  if(comLines.length)text+="\n\nКомментарии к фото:\n"+comLines.join("\n");
  const fileLabel="selection_"+GALLERY+".txt";   // только ASCII: имена с кириллицей браузеры сохраняют не везде
  if(!WORKER&&!(TG_TOKEN&&TG_CHAT)){download(fileLabel,text);showFileSaved();return}
  sending=true;
  const btn=$("goBtn");btn.disabled=true;btn.textContent="Отправляю...";
  try{
    if(WORKER)await viaWorker(text,name,list.length);else await viaTelegram(text);
    lastSent=signature();store.set(LSENT,lastSent);
    renderMeta();
    showSuccess(list.length);
  }catch(e){
    showError(String(e.message||e),text,fileLabel);
  }finally{sending=false}
}
$("sendBtn").onclick=openForm;

document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){
    if($("dlg").classList.contains("open"))closeDlg();else closeLb();
    return;
  }
  if(!$("lb").classList.contains("open")||$("dlg").classList.contains("open"))return;
  const t=e.target&&e.target.tagName;
  if(t==="INPUT"||t==="TEXTAREA"||t==="SELECT")return;
  if(e.key==="ArrowLeft")step(-1);
  if(e.key==="ArrowRight")step(1);
  if(e.key===" "){e.preventDefault();toggle(cur)}
});
render();
(function(){            // статистика просмотров: только если подключён Worker
  if(!WORKER)return;
  const post=o=>{try{
    const b=JSON.stringify(Object.assign({slug:SLUG},o));
    if(navigator.sendBeacon)navigator.sendBeacon(WORKER+"/view",new Blob([b],{type:"text/plain;charset=UTF-8"}));
    else fetch(WORKER+"/view",{method:"POST",body:b,keepalive:true,headers:{"Content-Type":"text/plain;charset=UTF-8"}}).catch(()=>{});
  }catch(e){}};
  let seen=false;try{seen=sessionStorage.getItem("v_"+SLUG)==="1"}catch(e){}
  if(!seen){post({event:"open"});try{sessionStorage.setItem("v_"+SLUG,"1")}catch(e){}}
  document.addEventListener("visibilitychange",()=>{
    if(document.visibilityState==="hidden")post({event:"leave",selected:sel.size,comments:comCount()});
  });
})();
</script></body></html>
"""


# ---------------------------------------------------------------- папки и файлы данных

def app_dir():
    env = os.environ.get("PHOTOGALLERY_HOME")
    if env:
        d = Path(env)
    else:
        base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
                or str(Path.home() / ".local" / "share"))
        d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA = app_dir()
CONFIG_PATH = DATA / "config.json"
REGISTRY_PATH = DATA / "clients.json"
PORTFOLIO_PATH = DATA / "portfolio.json"
CACHE_DIR = DATA / "cache"
LOG_PATH = DATA / "gallery.log"

DEFAULT_CONFIG = {
    "account_id": "", "access_key_id": "", "secret_access_key": "",
    "bucket": "photos", "public_url": "",
    "telegram_token": "", "telegram_chat_id": "", "worker_url": "",
    "photoshop_path": "", "lightroom_path": "",
    "title": DEFAULT_TITLE, "max_select": 0, "view_size": 1600,
    "out_root": str(Path.home() / "Documents" / "PhotoGallery_selected"),
    "expire_days": 0, "cloud_limit_gb": 10, "price_color": "", "price_retouch": "", "price_comment": "",
    "discount_tiers": "10:5, 20:10, 30:15", "currency": "€", "message": DEFAULT_MESSAGE, "endpoint": "",
}


class AppError(Exception):
    """Понятная пользователю ошибка (показываем текст как есть)."""


class Cancelled(Exception):
    pass


def file_log(msg):
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 2_000_000:
            LOG_PATH.replace(LOG_PATH.with_suffix(".old"))
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except ValueError:
        try:
            path.replace(path.with_suffix(path.suffix + ".bad"))
        except OSError:
            pass
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json(CONFIG_PATH, {}))
    return cfg


def save_config(cfg):
    save_json(CONFIG_PATH, cfg)


def load_registry():
    return load_json(REGISTRY_PATH, {})


def save_registry(reg):
    save_json(REGISTRY_PATH, reg)


def cloud_ready(cfg):
    need = all(cfg.get(k) for k in ("access_key_id", "secret_access_key", "bucket", "public_url"))
    return bool(need and (cfg.get("account_id") or cfg.get("endpoint")))


# ---------------------------------------------------------------- мелкие помощники

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def fmt_size(n):
    n = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if n < 1024 or unit == "ТБ":
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s.lower())]


def check_name(name):
    name = (name or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", name):
        raise AppError("Имя клиента: только латинские буквы, цифры, дефис и подчёркивание "
                       "(например anna-2026), без пробелов.")
    return name


def safe_rel(name):
    """Имя из письма: только относительный путь без '..' (письмо мог подделать кто угодно)."""
    if not name or "\\" in name or ":" in name:
        return False
    p = PurePosixPath(name)
    return not p.is_absolute() and ".." not in p.parts


def open_path(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- Photoshop / Lightroom

APPS = {
    "photoshop": {"title": "Photoshop", "cfg": "photoshop_path"},
    "lightroom": {"title": "Lightroom", "cfg": "lightroom_path"},
}


def _win_registry_path(exe_name):
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return ""
    sub = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + exe_name
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | view) as k:
                    val = str(winreg.QueryValueEx(k, "")[0]).strip().strip('"')
                if val and Path(val).is_file():
                    return val
            except OSError:
                continue
    return ""


def _newest(paths):
    paths = [p for p in paths if "beta" not in str(p).lower()]
    return str(sorted(paths, reverse=True)[0]) if paths else ""


def find_app(key):
    """Ищет установленный Photoshop / Lightroom. Пустая строка, если не нашли."""
    try:
        if sys.platform.startswith("win"):
            pats = {"photoshop": ["Adobe/Adobe Photoshop*/Photoshop.exe"],
                    "lightroom": ["Adobe/Adobe Lightroom Classic/Lightroom.exe",
                                  "Adobe/Adobe Lightroom/lightroom.exe"]}[key]
            roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"),
                     os.environ.get("ProgramFiles(x86)"), "C:\\Program Files"]
            roots = list(dict.fromkeys(r for r in roots if r))
            for pat in pats:
                for r in roots:
                    hit = _newest(list(Path(r).glob(pat)))
                    if hit:
                        return hit
            names = {"photoshop": ["Photoshop.exe"], "lightroom": ["Lightroom.exe", "lightroom.exe"]}[key]
            for n in names:
                p = _win_registry_path(n) or shutil.which(n) or ""
                if p:
                    return p
        elif sys.platform == "darwin":
            pats = {"photoshop": ["Adobe Photoshop*/Adobe Photoshop*.app"],
                    "lightroom": ["Adobe Lightroom Classic/Adobe Lightroom Classic.app",
                                  "Adobe Lightroom.app"]}[key]
            for pat in pats:
                hit = _newest(list(Path("/Applications").glob(pat)))
                if hit:
                    return hit
    except Exception:  # noqa: BLE001
        pass
    return ""


def resolve_app(cfg, key):
    """Путь из настроек, если он верный, иначе автопоиск."""
    p = str(cfg.get(APPS[key]["cfg"]) or "").strip().strip('"')
    if p and Path(p).exists():
        return p
    return find_app(key)


def launch_app(path):
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", str(path)])
    else:
        subprocess.Popen([str(path)])


def app_icon_png(path, px=24):
    """Значок самой программы (как в проводнике), PNG-байты. None, если достать не вышло."""
    try:
        cache = DATA / "icons"
        cache.mkdir(parents=True, exist_ok=True)
        tag = re.sub(r"\W+", "_", f"{path}_{int(Path(path).stat().st_mtime)}")[-90:]
        out = cache / f"{tag}.png"
        if not out.is_file():
            if sys.platform.startswith("win"):
                ps = ("Add-Type -AssemblyName System.Drawing; "
                      "$i=[System.Drawing.Icon]::ExtractAssociatedIcon($env:PG_EXE); "
                      "$i.ToBitmap().Save($env:PG_OUT,[System.Drawing.Imaging.ImageFormat]::Png)")
                subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                                "-Command", ps], env=dict(os.environ, PG_EXE=str(path), PG_OUT=str(out)),
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=25,
                               creationflags=0x08000000)
            elif sys.platform == "darwin":
                icns = sorted(Path(path).glob("Contents/Resources/*.icns"))
                if icns:
                    from PIL import Image
                    Image.open(icns[0]).convert("RGBA").save(out, "PNG")
        if not out.is_file():
            return None
        try:
            from PIL import Image
            im = Image.open(out).convert("RGBA")
            im = im.resize((px, px), getattr(Image, "Resampling", Image).LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return buf.getvalue()
        except ImportError:
            return out.read_bytes()
    except Exception:  # noqa: BLE001
        return None


def symbol_png(kind, color, px=22):
    """Маленькая линейная иллюстрация для кнопок (рисуется в коде). None, если нет Pillow."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    S = 8
    im = Image.new("RGBA", (24 * S, 24 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = int(1.9 * S)

    def P(*a):
        return [v * S for v in a]

    if kind == "upload":            # лоток со стрелкой вверх
        d.line(P(4, 15, 4, 20, 20, 20, 20, 15), fill=color, width=w, joint="curve")
        d.line(P(12, 16, 12, 5), fill=color, width=w)
        d.line(P(7.5, 9, 12, 4.5, 16.5, 9), fill=color, width=w, joint="curve")
    elif kind == "select":          # кружок с галочкой
        d.ellipse(P(3, 3, 21, 21), outline=color, width=w)
        d.line(P(8, 12.5, 11, 15.5, 16.5, 9), fill=color, width=w, joint="curve")
    elif kind == "gift":            # подарочная коробка
        d.rectangle(P(4.5, 11, 19.5, 20.5), outline=color, width=w)
        d.rectangle(P(3, 7.5, 21, 11), outline=color, width=w)
        d.line(P(12, 7.5, 12, 20.5), fill=color, width=w)
        d.ellipse(P(7, 3, 12, 7.5), outline=color, width=int(1.5 * S))
        d.ellipse(P(12, 3, 17, 7.5), outline=color, width=int(1.5 * S))
    elif kind == "portfolio":       # звезда
        import math
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            r = 9.5 if i % 2 == 0 else 4.2
            pts += [12 + r * math.cos(a), 12.8 + r * math.sin(a)]
        d.line(P(*(pts + pts[:2])), fill=color, width=w, joint="curve")
    elif kind == "clients":         # человек
        d.ellipse(P(8, 3.5, 16, 11.5), outline=color, width=w)
        d.arc(P(4, 13.5, 20, 29.5), 180, 360, fill=color, width=w)
    elif kind == "settings":        # ползунки
        for y, x in ((6, 15), (12, 8), (18, 16)):
            d.line(P(4, y, 20, y), fill=color, width=int(1.5 * S))
            d.ellipse(P(x - 2.6, y - 2.6, x + 2.6, y + 2.6), fill=color)
    else:                           # "photo": рамка с горой и солнцем
        d.rounded_rectangle(P(3, 4, 21, 20), radius=3 * S, outline=color, width=w)
        d.polygon(P(5.5, 18, 10, 11.5, 13.5, 16, 15.5, 13.5, 18.5, 18), fill=color)
        d.ellipse(P(14.5, 6.5, 17.5, 9.5), fill=color)
    im = im.resize((px, px), getattr(Image, "Resampling", Image).LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def link_for(cfg, entry):
    return f"{cfg['public_url'].rstrip('/')}/{entry['slug']}/index.html"


def age_days(entry):
    try:
        return (datetime.now() - datetime.strptime(entry["created"], "%Y-%m-%d %H:%M")).days
    except (KeyError, ValueError):
        return 0


def new_entry(name, src, mode, max_select, watermark, plain=False):
    slug = name if plain else f"{name}-{secrets.token_hex(5)}"
    return {"slug": slug, "src": str(src), "created": now_str(), "mode": mode,
            "max": int(max_select), "watermark": watermark, "published": ""}


def is_raw(rel):
    return Path(rel).suffix.lower() in RAW_EXT


def list_photos(src, raw=True):
    rels = []
    allowed = EXT if raw else EXT - RAW_EXT
    for p in Path(src).rglob("*"):
        if p.is_file() and p.suffix.lower() in allowed:
            rel = p.relative_to(src)
            if "_thumbs" in rel.parts:
                continue
            rels.append(rel.as_posix())
    rels.sort(key=natural_key)
    return rels


# ---------------------------------------------------------------- контекст фоновой задачи

class Ctx:
    """Связь фоновой задачи с окном: лог, прогресс, отмена."""

    def __init__(self, emit, cancel):
        self.emit, self.cancel = emit, cancel
        self._last = 0.0
        self._lock = threading.Lock()

    def log(self, msg):
        self.emit(("log", msg))

    def progress(self, label, done, total, bdone=0, btotal=0, force=False):
        with self._lock:
            now = time.time()
            if not force and now - self._last < 0.15:
                return
            self._last = now
        self.emit(("progress", label, done, total, bdone, btotal))

    def check(self):
        if self.cancel.is_set():
            raise Cancelled()


def run_parallel(ctx, label, items, func, workers=UPLOAD_WORKERS, size_of=None):
    """func(item) в потоках. Возвращает [(item, ошибка)]. Учитывает кнопку «Остановить»."""
    errors = []
    if not items:
        return errors
    total = len(items)
    btotal = sum(size_of(i) for i in items) if size_of else 0
    done = bdone = 0
    ctx.progress(label, 0, total, 0, btotal, force=True)
    ex = cf.ThreadPoolExecutor(max_workers=workers)
    futures = {ex.submit(func, it): it for it in items}
    try:
        for fut in cf.as_completed(futures):
            it = futures[fut]
            try:
                fut.result()
            except cf.CancelledError:
                continue
            except Exception as e:  # noqa: BLE001
                errors.append((it, e))
            done += 1
            if size_of:
                bdone += size_of(it)
            ctx.progress(label, done, total, bdone, btotal)
            if ctx.cancel.is_set():
                for f in futures:
                    f.cancel()
                break
    finally:
        ex.shutdown(wait=True)
    ctx.progress(label, done, total, bdone, btotal, force=True)
    ctx.check()
    return errors


# ---------------------------------------------------------------- облако (R2)

def s3_client(cfg):
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise AppError("Не установлен boto3. Выполни:  pip install pillow boto3")
    kw = dict(signature_version="s3v4", retries={"max_attempts": 10, "mode": "standard"},
              max_pool_connections=64)
    try:
        # новые boto3 добавляют контрольные суммы, с которыми R2 иногда не дружит
        conf = Config(request_checksum_calculation="when_required",
                      response_checksum_validation="when_required", **kw)
    except TypeError:
        conf = Config(**kw)
    endpoint = cfg.get("endpoint") or f"https://{cfg['account_id']}.r2.cloudflarestorage.com"
    return boto3.client("s3", endpoint_url=endpoint, region_name="auto",
                        aws_access_key_id=cfg["access_key_id"],
                        aws_secret_access_key=cfg["secret_access_key"], config=conf)


def list_keys(cfg, s3, prefix):
    out = {}
    try:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=cfg["bucket"], Prefix=prefix):
            for obj in page.get("Contents", []):
                out[obj["Key"]] = obj["Size"]
    except Exception as e:  # noqa: BLE001
        raise AppError(f"Не удалось связаться с облаком: {e}\nПроверь вкладку «Настройки».")
    return out


def require_cloud(cfg):
    if not cloud_ready(cfg):
        raise AppError("Сначала заполни и сохрани настройки облака (вкладка «Настройки»).")


# ---------------------------------------------------------------- превью и копии для просмотра

def add_watermark(im, text):
    from PIL import Image, ImageDraw, ImageFont
    w, h = im.size
    fsize = max(14, int(min(w, h) * 0.05))
    font = None
    for fname in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(fname, fsize)
            break
        except Exception:  # noqa: BLE001
            pass
    if font is None:
        try:
            font = ImageFont.load_default(size=fsize)
        except TypeError:
            font = ImageFont.load_default()
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    box = tmp.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    stepx, stepy = int(tw * 1.8) + 10, int(th * 5) + 10
    diag = int((w * w + h * h) ** 0.5) + 2
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y, row = 0, 0
    while y < diag:
        x = -(row % 2) * (stepx // 2)
        while x < diag:
            d.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 80))
            d.text((x, y), text, font=font, fill=(255, 255, 255, 110))
            x += stepx
        y += stepy
        row += 1
    layer = layer.rotate(30, resample=Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - h) // 2
    layer = layer.crop((left, top, left + w, top + h))
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def open_raw(path):
    """RAW (ARW и др.) -> PIL-картинка. Берём готовый JPEG-превью из файла (быстро), иначе проявляем."""
    try:
        import rawpy
    except ImportError:
        raise AppError("Для RAW (ARW) нужна библиотека rawpy. Выполни:  pip install rawpy")
    from PIL import Image
    with rawpy.imread(str(path)) as raw:
        flip = int(getattr(raw.sizes, "flip", 0) or 0)
        try:
            th = raw.extract_thumb()
            if th.format == rawpy.ThumbFormat.JPEG:
                im = Image.open(io.BytesIO(th.data))
                im.load()
                if not im.getexif().get(274):                     # в превью нет поворота: берём из RAW
                    im = im.rotate({3: 180, 5: 90, 6: 270}.get(flip, 0), expand=True)
                return im
            if th.format == rawpy.ThumbFormat.BITMAP:
                return Image.fromarray(th.data)
        except Exception:  # noqa: BLE001  (нет превью внутри файла)
            pass
        rgb = raw.postprocess(half_size=True, use_camera_wb=True, output_bps=8)
    return Image.fromarray(rgb)


def make_derivatives(src, targets, wm_text=""):
    """Открывает фото один раз и делает все копии. targets = [(путь, размер)].
    Возвращает множество путей, которые не получились."""
    todo = [(d, s) for d, s in targets if not (d.exists() and d.stat().st_size > 0)]
    if not todo:
        return set()
    try:
        from PIL import Image, ImageOps
        Image.MAX_IMAGE_PIXELS = None
        biggest = max(s for _, s in todo)
        if is_raw(src):
            base = ImageOps.exif_transpose(open_raw(src)).convert("RGB")
        else:
            with Image.open(src) as im:
                im.draft("RGB", (biggest * 2, biggest * 2))      # ускоряет чтение больших JPEG
                base = ImageOps.exif_transpose(im).convert("RGB")
    except AppError:
        raise
    except Exception:  # noqa: BLE001
        return {d for d, _ in todo}
    failed = set()
    for dst, size in todo:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            c = base.copy()
            c.thumbnail((size, size))
            if wm_text:
                c = add_watermark(c, wm_text)
            tmp = dst.with_name(dst.name + ".part")
            c.save(tmp, "JPEG", quality=82 if size > 1000 else 80, optimize=True)
            tmp.replace(dst)
        except Exception:  # noqa: BLE001
            failed.add(dst)
    return failed


def cache_dir(slug):
    return CACHE_DIR / slug


def thumb_file(slug, rel):
    return cache_dir(slug) / "_thumbs" / (rel + ".jpg")


def view_file(slug, rel):
    return cache_dir(slug) / "_view" / (rel + ".jpg")


def ensure_cache_params(cfg, entry):
    """Если изменились папка, режим, размер или водяной знак, старые копии неактуальны."""
    slug = entry["slug"]
    params = {"src": entry["src"], "mode": entry["mode"], "wm": entry.get("watermark", ""),
              "view": int(cfg.get("view_size") or 1600), "thumb": THUMB_SIZE}
    pfile = cache_dir(slug) / "params.json"
    if load_json(pfile, None) != params:
        shutil.rmtree(cache_dir(slug) / "_thumbs", ignore_errors=True)
        shutil.rmtree(cache_dir(slug) / "_view", ignore_errors=True)
        save_json(pfile, params)


def load_state(entry):
    return load_json(cache_dir(entry["slug"]) / "state.json", None)


# ---------------------------------------------------------------- страница

def build_page(cfg, entry, name, photos):
    data = json.dumps(photos, ensure_ascii=False).replace("</", "<\\/")
    worker = (cfg.get("worker_url") or "").strip().rstrip("/")
    # с Worker токен Telegram на страницу не попадает: уведомления шлёт сам Worker
    token = "" if worker else (cfg.get("telegram_token", "") or "")
    chat = "" if worker else str(cfg.get("telegram_chat_id", "") or "")
    return (TEMPLATE.replace("__TITLE__", html_escape(cfg.get("title") or DEFAULT_TITLE))
            .replace("__TG_TOKEN__", json.dumps(token))
            .replace("__TG_CHAT__", json.dumps(chat))
            .replace("__WORKER__", json.dumps(worker).replace("</", "<\\/"))
            .replace("__SLUG__", entry["slug"])
            .replace("__PORTFOLIO__", "true" if portfolio_published() else "false")
            .replace("__PRICES__", json.dumps({k: str(cfg.get("price_" + k) or "").strip() for k in SERVICES},
                                              ensure_ascii=False).replace("</", "<\\/"))
            .replace("__PRICING__", json.dumps(pricing(cfg), ensure_ascii=False))
            .replace("__MAX__", str(int(entry.get("max") or 0)))
            .replace("__GALLERY__", name)
            .replace("__PHOTOS__", data))


def page_photos(entry, state):
    """Список для страницы + ключи, которые должны лежать в облаке."""
    slug, view = entry["slug"], entry["mode"] == MODE_VIEW
    ft, fv = set(state["failed_thumb"]), set(state["failed_view"])
    photos, needed = [], []
    for rel in state["rels"]:
        if view or is_raw(rel):          # RAW браузер не показывает: всегда JPEG-копия
            if rel in fv:
                continue
            full = f"_view/{rel}.jpg"
        else:
            full = rel
        thumb = full if rel in ft else f"_thumbs/{rel}.jpg"
        photos.append({"n": rel, "t": quote(thumb), "f": quote(full)})
        needed.append(f"{slug}/{full}")
        if rel not in ft:
            needed.append(f"{slug}/_thumbs/{rel}.jpg")
    return photos, needed


# ---------------------------------------------------------------- операции

def op_thumbs(ctx, cfg, entry):
    src = Path(entry["src"])
    if not src.is_dir():
        raise AppError(f"Папка с фото не найдена: {src}")
    rels = list_photos(src)
    if not rels:
        raise AppError("В папке нет фото (jpg, png, webp, RAW: ARW, CR2, NEF, DNG и др.).")
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise AppError("Не установлен Pillow. Выполни:  pip install pillow boto3")
    slug = entry["slug"]
    ensure_cache_params(cfg, entry)
    view = entry["mode"] == MODE_VIEW
    wm = entry.get("watermark", "") if view else ""
    vsize = int(cfg.get("view_size") or 1600)
    ctx.log(f"Фото в папке: {len(rels)}, общий размер "
            f"{fmt_size(sum((src / r).stat().st_size for r in rels))}")
    nraw = sum(1 for r in rels if is_raw(r))
    if nraw:
        ctx.log(f"RAW-файлов: {nraw}. В облако уйдут только JPEG-копии для просмотра, оригиналы RAW "
                "останутся у тебя и при скачивании выбора копируются из папки.")
    failed_thumb, failed_view = set(), set()

    def job(rel):
        vw = view or is_raw(rel)
        targets = [(thumb_file(slug, rel), THUMB_SIZE)]
        if vw:
            targets.append((view_file(slug, rel), vsize))
        bad = make_derivatives(src / rel, targets, wm if vw else "")
        if thumb_file(slug, rel) in bad:
            failed_thumb.add(rel)
        if vw and view_file(slug, rel) in bad:
            failed_view.add(rel)

    run_parallel(ctx, "Превью", rels, job, workers=min(os.cpu_count() or 4, 8))
    if failed_thumb or failed_view:
        ctx.log(f"Не открылись как изображения: {len(failed_thumb | failed_view)} шт. "
                + ("(в режиме просмотра они пропущены)" if view else "(вместо превью будет оригинал)"))
    state = {"rels": rels, "failed_thumb": sorted(failed_thumb), "failed_view": sorted(failed_view)}
    save_json(cache_dir(slug) / "state.json", state)
    ctx.log("Превью готовы.")
    return state


def op_upload(ctx, cfg, entry):
    require_cloud(cfg)
    state = op_thumbs(ctx, cfg, entry)
    s3 = s3_client(cfg)
    slug, src = entry["slug"], Path(entry["src"])
    view = entry["mode"] == MODE_VIEW
    ft, fv = set(state["failed_thumb"]), set(state["failed_view"])
    jobs = []
    for rel in state["rels"]:
        if view or is_raw(rel):
            if rel in fv:
                continue
            jobs.append((view_file(slug, rel), f"{slug}/_view/{rel}.jpg", "image/jpeg"))
        else:
            p = src / rel
            jobs.append((p, f"{slug}/{rel}", CONTENT_TYPES[p.suffix.lower()]))
        if rel not in ft:
            jobs.append((thumb_file(slug, rel), f"{slug}/_thumbs/{rel}.jpg", "image/jpeg"))
    if not jobs:
        raise AppError("Нет файлов для загрузки.")
    ctx.log("Смотрю, что уже есть в облаке...")
    existing = list_keys(cfg, s3, f"{slug}/")
    todo = [j for j in jobs if existing.get(j[1]) != j[0].stat().st_size]
    ctx.log(f"Уже в облаке: {len(jobs) - len(todo)} файлов, загружаю: {len(todo)}")
    from boto3.s3.transfer import TransferConfig
    tc = TransferConfig(multipart_threshold=64 * 1024 * 1024, multipart_chunksize=64 * 1024 * 1024,
                        max_concurrency=4)

    def upload_job(job):
        path, key, ctype = job
        s3.upload_file(str(path), cfg["bucket"], key,
                       ExtraArgs={"ContentType": ctype, "CacheControl": PHOTO_CACHE}, Config=tc)

    errors = run_parallel(ctx, "Загрузка", todo, upload_job, size_of=lambda j: j[0].stat().st_size)
    if errors:
        job, e = errors[0]
        raise AppError(f"Не загрузилось файлов: {len(errors)}. Пример: {job[1]}: {e}\n"
                       "Нажми «Загрузить в облако» ещё раз: загрузка продолжится.")
    ctx.log("Все файлы в облаке.")
    return state


def op_page(ctx, cfg, entry, name):
    require_cloud(cfg)
    state = load_state(entry)
    if not state:
        raise AppError("Сначала создай превью и загрузи фото в облако.")
    photos, needed = page_photos(entry, state)
    if not photos:
        raise AppError("В галерее нет фото.")
    s3 = s3_client(cfg)
    existing = list_keys(cfg, s3, f"{entry['slug']}/")
    missing = [k for k in needed if k not in existing]
    if missing:
        raise AppError(f"В облаке не хватает файлов: {len(missing)}. Нажми «Загрузить в облако».")
    html = build_page(cfg, entry, name, photos)
    s3.put_object(Bucket=cfg["bucket"], Key=f"{entry['slug']}/index.html", Body=html.encode("utf-8"),
                  ContentType="text/html; charset=utf-8", CacheControl="no-cache")
    ctx.log(f"Страница опубликована ({len(photos)} фото).")
    if (cfg.get("worker_url") or "").strip():
        ctx.log("Выбор клиента придёт через Worker (токен Telegram на страницу не попадает). "
                "Приложение подхватит выбор само: вкладка «Выбор клиента».")
    elif cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
        ctx.log("ВНИМАНИЕ: токен Telegram вставлен в код страницы и виден любому, у кого есть ссылка. "
                "Безопаснее подключить Worker (см. инструкцию).")
    else:
        ctx.log("ВНИМАНИЕ: Telegram не настроен. Клиент сможет только скачать файл со списком и "
                "переслать его вручную. Подключи Worker или Telegram в «Настройках» и обнови страницу.")
    return link_for(cfg, entry)


def op_all(ctx, cfg, entry, name):
    op_upload(ctx, cfg, entry)
    ctx.check()
    ctx.log("Публикую страницу...")
    return op_page(ctx, cfg, entry, name)


def parse_price(txt):
    """Первое число из текста цены: «5 € за фото» -> 5.0; «бесплатно» -> 0."""
    m = re.search(r"\d+(?:[.,]\d+)?", str(txt or ""))
    return float(m.group().replace(",", ".")) if m else 0.0


def parse_tiers(txt):
    """«10:5, 20:10, 30:15» -> [(10, 5.0), (20, 10.0), (30, 15.0)]: от N фото скидка P %."""
    out = {}
    for n, p in re.findall(r"(\d+)\s*[:=\-]\s*(\d+(?:[.,]\d+)?)", str(txt or "")):
        n, p = int(n), float(p.replace(",", "."))
        if n >= 1 and 0 < p <= 90:
            out[n] = p
    return sorted(out.items())


def pricing(cfg):
    return {"num": {k: parse_price(cfg.get("price_" + k)) for k in SERVICES},
            "tiers": [[n, p] for n, p in parse_tiers(cfg.get("discount_tiers"))],
            "cur": str(cfg.get("currency") or "").strip()}


def calc_total(counts, pr):
    """counts = {услуга: число фото}. Скидка считается по числу фото с платной услугой и действует на всю сумму."""
    sub = sum(counts.get(k, 0) * pr["num"].get(k, 0) for k in SERVICES)
    paid = sum(counts.get(k, 0) for k in SERVICES if pr["num"].get(k, 0) > 0)
    pct = 0.0
    for n, p in pr["tiers"]:
        if paid >= n:
            pct = p
    disc = int(sub * pct + 0.5) / 100
    return {"sub": sub, "paid": paid, "pct": pct, "disc": disc, "total": sub - disc}


def parse_email(text):
    part = text.split("Файлы:")[-1] if "Файлы:" in text else text
    comments, services = {}, {}
    pieces = re.split("(" + re.escape(COMMENTS_MARK) + "|" + re.escape(SERVICES_MARK) + ")", part)
    part = pieces[0]
    for mark, body in zip(pieces[1::2], pieces[2::2]):
        for ln in body.splitlines():
            n, sep, c = ln.strip().rpartition(" | ")
            n, c = n.strip(), c.strip()
            if not (sep and n and c and safe_rel(n)):
                continue
            if mark == COMMENTS_MARK:
                comments[n] = c
            elif c.lower() in SERVICE_BY_NAME:
                services[n] = SERVICE_BY_NAME[c.lower()]
    exts = tuple(EXT)
    names = [ln.strip() for ln in part.splitlines() if ln.strip().lower().endswith(exts)]
    names = list(dict.fromkeys(names))
    m = re.search(r"Клиент:[ \t]*(.+)", text)
    client = m.group(1).strip() if m else ""
    m = re.search(r"Галерея:[ \t]*([A-Za-z0-9_-]+)", text)
    gallery = m.group(1).strip().lower() if m else ""
    m = re.search(r"Выбрано:[ \t]*(\d+)", text)
    declared = int(m.group(1)) if m else None
    m = re.search(r"Итого:[ \t]*(\d+(?:[.,]\d+)?)", text)
    client_total = float(m.group(1).replace(",", ".")) if m else None
    safe = [n for n in names if safe_rel(n)]
    return {"names": safe, "rejected": [n for n in names if not safe_rel(n)],
            "client": client, "gallery": gallery, "declared": declared, "comments": comments,
            "client_total": client_total,
            "services": {n: services.get(n, "color") for n in safe} if services else {}}


def op_download(ctx, cfg, entry, names, out, prefer_local=True, comments=None, services=None):
    """services = {имя: color|retouch|comment}: если задано, фото раскладываются по папкам услуг."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    slug, src = entry["slug"], Path(entry["src"])
    view = entry["mode"] == MODE_VIEW
    s3 = s3_client(cfg) if cloud_ready(cfg) else None
    counts = {"local": 0, "cloud": 0}
    lock = threading.Lock()

    def target(n):
        return out / SERVICES[services.get(n, "color")] if services else out

    def job(n):
        local = src / n
        if prefer_local and local.is_file():
            dst = target(n) / n
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, dst)
            with lock:
                counts["local"] += 1
            return
        if s3 is None:
            raise FileNotFoundError("нет на компьютере, а облако не настроено")
        if view or is_raw(n):
            key, dst = f"{slug}/_view/{n}.jpg", target(n) / (n + ".preview.jpg")
        else:
            key, dst = f"{slug}/{n}", target(n) / n
        dst.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(cfg["bucket"], key, str(dst))
        with lock:
            counts["cloud"] += 1

    errors = run_parallel(ctx, "Копирование", names, job, workers=6)
    ctx.log(f"Скопировано с компьютера: {counts['local']}, скачано из облака: {counts['cloud']}")
    if services:
        per = {k: sum(1 for n in names if services.get(n, "color") == k) for k in SERVICES}
        ctx.log("По папкам: " + ", ".join(f"{SERVICES[k]} {v}" for k, v in per.items() if v))
    if counts["cloud"] and (view or any(is_raw(n) for n in names)):
        ctx.log("Внимание: из облака скачаны копии для просмотра (оригиналов в облаке нет).")
    if comments:
        lines = [f"{n}: {c}" for n, c in comments.items()]
        cdir = out / SERVICES["comment"] if services else out
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / COMMENTS_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
        ctx.log(f"Комментарии клиента ({len(lines)}) сохранены в файл {COMMENTS_FILE}")
    return {"ok": len(names) - len(errors), "total": len(names),
            "missing": [n for n, _ in errors], "out": str(out)}


def op_close(ctx, cfg, entry):
    require_cloud(cfg)
    s3 = s3_client(cfg)
    slug = entry["slug"]
    keys = list(list_keys(cfg, s3, f"{slug}/"))              # фото, страница, выдача (_final)
    keys += list(list_keys(cfg, s3, f"{INBOX_DIR}/{slug}/"))  # выборы клиента
    keys.append(f"{STATS_DIR}/{slug}.json")                   # статистика просмотров (если нет, не страшно)
    ctx.log(f"Удаляю из облака файлов: {len(keys)}")
    batches = [keys[i:i + 1000] for i in range(0, len(keys), 1000)]

    def del_batch(batch):
        try:
            s3.delete_objects(Bucket=cfg["bucket"],
                              Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True})
        except Exception:  # noqa: BLE001
            for k in batch:
                s3.delete_object(Bucket=cfg["bucket"], Key=k)

    errors = run_parallel(ctx, "Удаление", batches, del_batch, workers=4)
    if errors:
        raise AppError(f"Часть файлов не удалена ({errors[0][1]}). Запусти ещё раз.")
    shutil.rmtree(cache_dir(entry["slug"]), ignore_errors=True)
    ctx.log("Клиент удалён из облака, ссылка больше не работает.")
    return len(keys)


def op_stats(ctx, cfg, entry):
    require_cloud(cfg)
    keys = list_keys(cfg, s3_client(cfg), f"{entry['slug']}/")
    total = sum(keys.values())
    cost = total / 1024 ** 3 * R2_PRICE_PER_GB
    return {"files": len(keys), "bytes": total, "cost": cost}


def op_test(ctx, cfg):
    require_cloud(cfg)
    s3 = s3_client(cfg)
    try:
        s3.list_objects_v2(Bucket=cfg["bucket"], MaxKeys=1)
    except Exception as e:  # noqa: BLE001
        raise AppError(f"Не удалось подключиться: {e}")
    return "Подключение к облаку работает."


def op_prepare_phone(ctx, cfg):
    """Один раз: CORS для приложения «Съёмки» + список клиентов для подсказок."""
    require_cloud(cfg)
    s3 = s3_client(cfg)
    try:
        s3.put_bucket_cors(Bucket=cfg["bucket"], CORSConfiguration={"CORSRules": [{
            "AllowedOrigins": ["https://localhost", "http://localhost", "capacitor://localhost"],
            "AllowedMethods": ["GET", "PUT", "DELETE", "HEAD"],
            "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 86400}]})
    except Exception as e:  # noqa: BLE001
        raise AppError("Не удалось включить CORS (нужны права Admin Read & Write у API-токена). "
                       f"Можно добавить правило вручную в Cloudflare → бакет → Settings → CORS. {e}")
    names = sorted(load_registry().keys())
    s3.put_object(Bucket=cfg["bucket"], Key="_calendar/clients.json",
                  Body=json.dumps(names, ensure_ascii=False).encode("utf-8"), ContentType="application/json")
    return f"Бакет готов для телефона. Клиентов передано: {len(names)}."


def phone_settings_json(cfg):
    return json.dumps({"account": cfg.get("account_id", ""), "access": cfg.get("access_key_id", ""),
                       "secret": cfg.get("secret_access_key", ""), "bucket": cfg.get("bucket", "")},
                      ensure_ascii=False)


def op_test_telegram(ctx, cfg):
    import urllib.request
    import urllib.error
    token, chat = cfg.get("telegram_token", ""), str(cfg.get("telegram_chat_id", ""))
    if not token or not chat:
        raise AppError("Заполни токен бота и Chat ID Telegram и сохрани настройки.")
    body = json.dumps({"chat_id": chat, "text": "Photo Gallery: тест связи, всё работает."}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            j = {"description": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        raise AppError(f"Нет связи с Telegram: {e}")
    if not j.get("ok"):
        raise AppError(f"Telegram ответил ошибкой: {j.get('description', j)}\n"
                       "Проверь токен и Chat ID, и что ты нажал Start у своего бота.")
    return "Тестовое сообщение отправлено в Telegram."


def fmt_iso(t):
    """Время из Worker (UTC, ISO) -> местное 'дд.мм чч:мм'."""
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return d.astimezone().strftime("%d.%m %H:%M")
    except (ValueError, TypeError, OSError):
        return str(t)[:16] if t else "-"


def read_json_key(cfg, s3, key):
    try:
        body = s3.get_object(Bucket=cfg["bucket"], Key=key)["Body"].read()
        data = json.loads(body.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001  (нет файла, битый json и т.п.)
        return None


def op_check_inbox(ctx, cfg, entries):
    """Ищет в облаке выборы клиентов (их кладёт Worker) и статистику просмотров.
    entries = {имя: запись клиента}. Возвращает {имя: {"new": [...], "stats": {...}, "submissions": N}}."""
    require_cloud(cfg)
    s3 = s3_client(cfg)
    result = {}
    for name, e in entries.items():
        ctx.check()
        slug = e["slug"]
        keys = list_keys(cfg, s3, f"{INBOX_DIR}/{slug}/")
        seen = set(e.get("seen") or [])
        new = []
        for k in sorted(k for k in keys if k not in seen):      # имена начинаются со времени
            d = read_json_key(cfg, s3, k)
            if d and d.get("text"):
                new.append({"key": k, "t": d.get("t", ""), "client": str(d.get("client", "")),
                            "count": int(d.get("count") or 0), "text": str(d["text"])})
        stats = read_json_key(cfg, s3, f"{STATS_DIR}/{slug}.json") or {}
        result[name] = {"new": new, "stats": stats, "submissions": len(keys)}
    return result


def op_cloud_usage(cfg):
    """Сколько занято в бакете: всего и по верхним папкам (клиенты, _portfolio, _inbox ...)."""
    s3 = s3_client(cfg)
    total, files, by = 0, 0, {}
    try:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=cfg["bucket"]):
            for o in page.get("Contents", []):
                total += o["Size"]
                files += 1
                top = o["Key"].split("/", 1)[0]
                by[top] = by.get(top, 0) + o["Size"]
    except Exception as e:  # noqa: BLE001
        raise AppError(f"Не удалось узнать занятое место: {e}")
    return {"bytes": total, "files": files, "by": by}


def op_test_worker(ctx, cfg):
    base = (cfg.get("worker_url") or "").strip().rstrip("/")
    if not base:
        raise AppError("Заполни адрес Worker и сохрани настройки.")
    req = urllib.request.Request(base + "/ping", headers={"User-Agent": "PhotoGallery/2"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AppError(f"Worker ответил ошибкой HTTP {e.code}. Проверь адрес и что код Worker "
                       "развёрнут (кнопка Deploy в Cloudflare).")
    except Exception as e:  # noqa: BLE001
        raise AppError(f"Нет связи с Worker: {e}")
    if not isinstance(j, dict) or not j.get("ok"):
        raise AppError("По этому адресу отвечает не Worker Photo Gallery. Проверь адрес.")
    if not j.get("r2"):
        raise AppError("Worker работает, но не подключён к бакету. В Cloudflare: Worker → Settings → "
                       "Bindings → Add → R2 bucket, имя переменной строго BUCKET, затем Deploy.")
    tg = ("Telegram-уведомления в Worker включены." if j.get("telegram")
          else "Telegram-уведомления в Worker выключены (они необязательны).")
    return f"Worker работает, доступ к бакету есть. {tg}"


def delivery_link(cfg, entry):
    return f"{cfg['public_url'].rstrip('/')}/{entry['slug']}/{FINAL_DIR}/index.html"


def file_sig(p):
    st = Path(p).stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def op_delivery(ctx, cfg, entry, name, folder, make_zip):
    """Выдача готовых фото: превью + файлы (+ ZIP) в <slug>/_final/ и страница со скачиванием."""
    require_cloud(cfg)
    src = Path(folder)
    if not src.is_dir():
        raise AppError(f"Папка не найдена: {src}")
    rels = list_photos(src, raw=False)
    if not rels:
        raise AppError("В папке нет фото (jpg, jpeg, png, gif, webp, bmp). RAW-файлы в выдачу не берутся: "
                       "сначала экспортируй готовые снимки в JPEG.")
    try:
        import PIL  # noqa: F401
    except ImportError:
        raise AppError("Не установлен Pillow. Выполни:  pip install pillow boto3")
    slug = entry["slug"]
    fdir = cache_dir(slug) / FINAL_DIR
    params = {"src": str(src), "thumb": THUMB_SIZE}
    if load_json(fdir / "params.json", None) != params:
        shutil.rmtree(fdir, ignore_errors=True)
        save_json(fdir / "params.json", params)
    total = sum((src / r).stat().st_size for r in rels)
    ctx.log(f"Готовых фото: {len(rels)}, общий размер {fmt_size(total)}")

    failed = set()

    def thumb_job(rel):
        t = fdir / "_thumbs" / (rel + ".jpg")
        try:
            if t.exists() and t.stat().st_mtime < (src / rel).stat().st_mtime:
                t.unlink()                      # фото переделали: превью устарело
        except OSError:
            pass
        if make_derivatives(src / rel, [(t, THUMB_SIZE)], ""):
            failed.add(rel)

    run_parallel(ctx, "Превью готовых фото", rels, thumb_job, workers=min(os.cpu_count() or 4, 8))

    jobs = []
    for rel in rels:
        p = src / rel
        jobs.append((p, f"{slug}/{FINAL_DIR}/{rel}", CONTENT_TYPES[p.suffix.lower()]))
        if rel not in failed:
            jobs.append((fdir / "_thumbs" / (rel + ".jpg"), f"{slug}/{FINAL_DIR}/_thumbs/{rel}.jpg", "image/jpeg"))

    zip_name, zip_size = "", 0
    if make_zip:
        zip_name = f"{name}-photos.zip"
        zpath = fdir / zip_name
        sigs = {r: file_sig(src / r) for r in rels}
        if not (zpath.exists() and load_json(fdir / "zip.json", None) == {"sigs": sigs}):
            free = shutil.disk_usage(fdir).free
            if free < total * 1.02 + 50 * 1024 * 1024:
                raise AppError(f"Не хватает места на диске для архива: нужно около {fmt_size(total)}, "
                               f"свободно {fmt_size(free)}. Освободи место или сними галочку ZIP.")
            ctx.log("Собираю ZIP-архив (JPEG уже сжаты, поэтому без пересжатия)...")
            tmp = zpath.with_name(zpath.name + ".part")
            try:
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
                    for i, r in enumerate(rels, 1):
                        ctx.check()
                        z.write(src / r, arcname=r)
                        ctx.progress("Архив", i, len(rels), force=(i == len(rels)))
                tmp.replace(zpath)
            except BaseException:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            save_json(fdir / "zip.json", {"sigs": sigs})
        zip_size = zpath.stat().st_size
        jobs.append((zpath, f"{slug}/{FINAL_DIR}/{zip_name}", "application/zip"))

    s3 = s3_client(cfg)
    ctx.log("Смотрю, что уже есть в облаке...")
    existing = list_keys(cfg, s3, f"{slug}/{FINAL_DIR}/")
    done = load_json(fdir / "uploaded.json", {})
    wanted = {j[1] for j in jobs}
    todo = [j for j in jobs if existing.get(j[1]) != j[0].stat().st_size or done.get(j[1]) != file_sig(j[0])]
    stale = [k for k in existing if k not in wanted and k != f"{slug}/{FINAL_DIR}/index.html"]
    ctx.log(f"Уже в облаке: {len(jobs) - len(todo)} файлов, загружаю: {len(todo)}"
            + (f", убираю устаревшие: {len(stale)}" if stale else ""))
    from boto3.s3.transfer import TransferConfig
    tc = TransferConfig(multipart_threshold=64 * 1024 * 1024, multipart_chunksize=64 * 1024 * 1024,
                        max_concurrency=4)

    def upload_job(job):
        path, key, ctype = job
        s3.upload_file(str(path), cfg["bucket"], key,
                       ExtraArgs={"ContentType": ctype, "CacheControl": "no-cache"}, Config=tc)

    errors = run_parallel(ctx, "Загрузка готовых фото", todo, upload_job,
                          size_of=lambda j: j[0].stat().st_size)
    failed_keys = {job[1] for job, _e in errors}
    for j in jobs:
        if j[1] not in failed_keys and (existing.get(j[1]) == j[0].stat().st_size or j in todo):
            done[j[1]] = file_sig(j[0])
    save_json(fdir / "uploaded.json", done)
    if errors:
        job, e = errors[0]
        raise AppError(f"Не загрузилось файлов: {len(errors)}. Пример: {job[1]}: {e}\n"
                       "Нажми кнопку ещё раз: загрузка продолжится.")
    for i in range(0, len(stale), 1000):
        s3.delete_objects(Bucket=cfg["bucket"], Delete={"Objects": [{"Key": k} for k in stale[i:i + 1000]],
                                                       "Quiet": True})

    photos = []
    for rel in rels:
        thumb = rel if rel in failed else f"_thumbs/{rel}.jpg"
        photos.append({"n": rel, "t": quote(thumb), "f": quote(rel)})
    html = (DELIVERY_TEMPLATE.replace("__TITLE__", FINAL_TITLE)
            .replace("__SLUG__", slug)
            .replace("__PORTFOLIO__", "true" if portfolio_published() else "false")
            .replace("__ZIPSIZE__", json.dumps(fmt_size(zip_size) if zip_name else ""))
            .replace("__ZIP__", json.dumps(quote(zip_name) if zip_name else ""))
            .replace("__PHOTOS__", json.dumps(photos, ensure_ascii=False).replace("</", "<\\/")))
    s3.put_object(Bucket=cfg["bucket"], Key=f"{slug}/{FINAL_DIR}/index.html", Body=html.encode("utf-8"),
                  ContentType="text/html; charset=utf-8", CacheControl="no-cache")
    ctx.log(f"Страница выдачи опубликована ({len(rels)} фото" + (", есть ZIP" if zip_name else "") + ").")
    return {"link": delivery_link(cfg, entry), "count": len(rels), "zip": zip_name, "zip_size": zip_size}


# ---------------------------------------------------------------- портфолио и отзывы

PF_DEFAULT = {"src": "", "title": "Портфолио", "about": "", "instagram": "", "telegram": "", "site": "",
              "email": "", "watermark": "", "published": "", "count": 0, "reviews": [], "handled": []}


def load_portfolio():
    pf = dict(PF_DEFAULT)
    d = load_json(PORTFOLIO_PATH, {})
    if isinstance(d, dict):
        pf.update(d)
    for k in ("reviews", "handled"):
        if not isinstance(pf.get(k), list):
            pf[k] = []
    return pf


def save_portfolio(pf):
    save_json(PORTFOLIO_PATH, pf)


def portfolio_published():
    return bool(load_portfolio().get("published"))


def portfolio_link(cfg):
    return f"{cfg['public_url'].rstrip('/')}/{PF_SLUG}/index.html"


def pf_entry(pf):
    """Портфолио грузится так же, как галерея в режиме «копии для просмотра»: оригиналы в облако не уходят."""
    return {"slug": PF_SLUG, "src": pf.get("src", ""), "mode": MODE_VIEW, "watermark": pf.get("watermark", "")}


def pf_contacts(pf):
    """Кнопки контактов для страницы; принимаются только ссылки http(s) и mailto."""
    out = []

    def add(label, url):
        if re.match(r"(https?://|mailto:)", url, re.I) and " " not in url:
            out.append({"l": label, "u": url})

    ig = (pf.get("instagram") or "").strip()
    if ig:
        add("Instagram", ig if re.match(r"https?://", ig, re.I)
            else "https://instagram.com/" + quote(ig.lstrip("@").strip("/"), safe="._-"))
    tg = (pf.get("telegram") or "").strip()
    if tg:
        if re.match(r"https?://", tg, re.I):
            add("Telegram", tg)
        else:
            add("Telegram", "https://t.me/" + quote(re.sub(r"^(https?://)?(t\.me/)?@?", "", tg).strip("/"), safe="._-"))
    site = (pf.get("site") or "").strip()
    if site:
        add("Сайт", site if re.match(r"https?://", site, re.I) else "https://" + site)
    mail = (pf.get("email") or "").strip()
    if mail and "@" in mail and " " not in mail:
        add("Написать", "mailto:" + mail)
    return out


def build_portfolio_page(cfg, pf, photos):
    reviews = [{"a": str(r.get("author", "")).strip()[:60], "t": str(r.get("text", "")).strip()[:1500],
                "r": max(1, min(5, int(r.get("rating") or 5))), "d": str(r.get("date", ""))[:20]}
               for r in pf.get("reviews", []) if str(r.get("text", "")).strip()]
    title = (pf.get("title") or "Портфолио").strip()
    data = {"title": title, "about": (pf.get("about") or "").strip(), "contacts": pf_contacts(pf),
            "photos": photos, "reviews": reviews,
            "worker": (cfg.get("worker_url") or "").strip().rstrip("/")}
    return (PORTFOLIO_TEMPLATE.replace("__TITLE__", html_escape(title))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))


def op_portfolio(ctx, cfg, pf):
    """Превью и копии работ -> _portfolio/, лишнее убирается, затем публикуется страница."""
    require_cloud(cfg)
    if not (pf.get("src") or "").strip():
        raise AppError("Выбери папку с лучшими работами.")
    entry = pf_entry(pf)
    state = op_upload(ctx, cfg, entry)
    photos, needed = page_photos(entry, state)
    if not photos:
        raise AppError("В портфолио нет фото.")
    s3 = s3_client(cfg)
    existing = list_keys(cfg, s3, f"{PF_SLUG}/")
    keep = set(needed) | {f"{PF_SLUG}/index.html"}
    stale = [k for k in existing if k not in keep]
    for i in range(0, len(stale), 1000):
        s3.delete_objects(Bucket=cfg["bucket"], Delete={"Objects": [{"Key": k} for k in stale[i:i + 1000]],
                                                       "Quiet": True})
    if stale:
        ctx.log(f"Убрано из облака лишних файлов портфолио: {len(stale)}")
    html = build_portfolio_page(cfg, pf, photos)
    s3.put_object(Bucket=cfg["bucket"], Key=f"{PF_SLUG}/index.html", Body=html.encode("utf-8"),
                  ContentType="text/html; charset=utf-8", CacheControl="no-cache")
    ctx.log(f"Страница портфолио опубликована (работ: {len(photos)}, отзывов: {len(pf.get('reviews', []))}).")
    if not (cfg.get("worker_url") or "").strip():
        ctx.log("Worker не подключён: клиенты не смогут оставлять отзывы со страницы, "
                "но отзывы, добавленные тобой вручную, на ней будут.")
    return {"link": portfolio_link(cfg), "count": len(photos)}


def op_check_reviews(ctx, cfg, handled):
    """Отзывы клиентов, которые оставили их через Worker и которые ты ещё не принял/отклонил."""
    require_cloud(cfg)
    s3 = s3_client(cfg)
    done = set(handled or [])
    out = []
    for k in sorted(k for k in list_keys(cfg, s3, f"{REVIEWS_DIR}/") if k not in done):
        ctx.check()
        d = read_json_key(cfg, s3, k)
        if d and d.get("text"):
            out.append({"key": k, "slug": k.split("/")[1] if k.count("/") >= 2 else "", "t": d.get("t", ""),
                        "author": str(d.get("author", "")), "rating": int(d.get("rating") or 5),
                        "text": str(d["text"])})
    return out


def delete_cloud_keys(cfg, keys):
    """Тихое удаление (отзывы после решения): ошибки не страшны, ключи уже помечены как разобранные."""
    try:
        s3 = s3_client(cfg)
        for k in keys:
            s3.delete_object(Bucket=cfg["bucket"], Key=k)
    except Exception as e:  # noqa: BLE001
        file_log(f"delete_cloud_keys: {e}")


def selftest():
    """Проверка собранного .exe: python gallery_app.py --selftest"""
    import io
    from PIL import Image
    s3 = s3_client({"account_id": "x", "access_key_id": "a", "secret_access_key": "b"})
    s3.meta.service_model.operation_names  # загружает данные botocore
    buf = io.BytesIO()
    Image.new("RGB", (100, 50), (1, 2, 3)).save(buf, "JPEG")
    out = "selftest ok"
    file_log(out)
    if sys.stdout:          # в сборке с --windowed консоли нет
        print(out)


# ================================================================ окно приложения

import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, simpledialog, ttk  # noqa: E402
import tkinter.font as tkfont  # noqa: E402


class ScrolledText(tk.Text):
    """Text с тёмной ttk-полосой прокрутки (как tkinter.scrolledtext, но под тему)."""

    def __init__(self, master=None, **kw):
        self.frame = ttk.Frame(master)
        self.vbar = ttk.Scrollbar(self.frame)
        self.vbar.pack(side="right", fill="y")
        kw.update({"yscrollcommand": self.vbar.set})
        super().__init__(self.frame, **kw)
        self.pack(side="left", fill="both", expand=True)
        self.vbar["command"] = self.yview
        own = vars(tk.Text).keys()
        for m in (vars(tk.Pack).keys() | vars(tk.Grid).keys() | vars(tk.Place).keys()) - own:
            if m[0] != "_" and m not in ("config", "configure"):
                setattr(self, m, getattr(self.frame, m))

    def __str__(self):
        return str(self.frame)


# палитра Velra: тёплые коричневые тона и голубые акценты
BG = "#3E2C23"        # основной фон (тёмный коричневый)
SIDEBAR = "#33241C"   # левая панель
PANEL = "#4A352A"     # заголовки, рамки
FIELD = "#2F2119"     # поля ввода
BTN = "#5B4133"       # обычные кнопки, блоки
BTN_HOVER = "#6C4F3F"
BORDER = "#6E5040"
TEXT = "#D9C3B1"      # текст (бежевый)
ACCENT = "#A7D8F0"    # основная кнопка (голубой)
ACCENT_HOVER = "#75C0E6"
ACCENT_DARK = "#5FAAD3"
ACCENT_OFF = "#4C6371"   # неактивная голубая кнопка
ON_ACCENT = "#3E2C23"    # текст на голубом
DIM = "#8E7766"          # неактивный текст
LIGHT = "#E6F4FB"
GREY = "#B09784"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self._set_window_icon()
        self.geometry("1360x900")
        self.minsize(1240, 780)
        self.cfg = load_config()
        self.reg = load_registry()
        self.q = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.task_cb = None
        self.last_clip = ""
        self.parsed = None
        self.inbox = {}          # имя клиента -> новые выборы из облака
        self.inbox_map = {}
        self.stats = {}          # имя клиента -> статистика просмотров
        self.loaded = None       # (клиент, ключ, текст) выбора, загруженного из облака
        self.checking = False
        self.pf = load_portfolio()
        self.pf_pending = []     # отзывы клиентов из облака, ждущие решения
        self.action_buttons = []
        self.report_callback_exception = self._on_callback_error

        self._apply_theme()

        self._build_ui()
        self._refresh_clients()
        self._load_settings_form()
        self._load_entry_form()
        self._pf_load_form()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self.after(500, self._startup_checks)
        self.after(4000, self._auto_check)
        self.after(50, self._dark_titlebar)

    # ------------------------------------------------------------ оформление

    def _set_window_icon(self):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PhotoGallery.App")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._icon64 = tk.PhotoImage(data=APP_ICON_B64)
            self.iconphoto(True, self._icon64)
        except tk.TclError:
            self._icon64 = None

    def _dark_titlebar(self):
        """Windows 10/11: тёмная строка заголовка окна (если система позволяет)."""
        try:
            import ctypes
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            val = ctypes.c_int(1)
            for attr in (20, 19):       # 20: Windows 11 / новые 10, 19: ранние сборки 10
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                    break
        except Exception:  # noqa: BLE001
            pass

    def _apply_theme(self):
        fams = set(tkfont.families())
        fam = next((f for f in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans") if f in fams), "TkDefaultFont")
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
            try:
                tkfont.nametofont(name).configure(family=fam, size=10)
            except tk.TclError:
                pass
        self.configure(bg=BG)
        for opt, val in (("*Text.background", FIELD), ("*Text.foreground", TEXT),
                         ("*Text.insertBackground", TEXT), ("*Text.selectBackground", ACCENT),
                         ("*Text.selectForeground", ON_ACCENT), ("*Text.relief", "flat"),
                         ("*Text.highlightThickness", 1), ("*Text.highlightBackground", BORDER),
                         ("*Text.highlightColor", ACCENT), ("*Text.padX", 8), ("*Text.padY", 6),
                         ("*TCombobox*Listbox.background", FIELD), ("*TCombobox*Listbox.foreground", TEXT),
                         ("*TCombobox*Listbox.selectBackground", ACCENT),
                         ("*TCombobox*Listbox.selectForeground", ON_ACCENT),
                         ("*TCombobox*Listbox.borderWidth", 0), ("*TCombobox*Listbox.relief", "flat")):
            self.option_add(opt, val)
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD, bordercolor=BORDER,
                     lightcolor=BG, darkcolor=BG, troughcolor=FIELD, focuscolor=ACCENT,
                     selectbackground=ACCENT, selectforeground=ON_ACCENT, insertcolor=TEXT)
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=TEXT)
        st.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid", borderwidth=1)
        st.configure("TLabelframe.Label", background=BG, foreground=ACCENT_HOVER, font=(fam, 10, "bold"))
        # вкладки переключаются кнопками в левой панели, штатные вкладки скрыты
        st.layout("TNotebook.Tab", [])
        st.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
                     bordercolor=BG, lightcolor=BG, darkcolor=BG, padding=0)
        # левая панель
        st.configure("Side.TButton", background=SIDEBAR, foreground=TEXT, bordercolor=SIDEBAR,
                     borderwidth=0, padding=(16, 11), relief="flat", anchor="w", font=(fam, 11),
                     focusthickness=0)
        st.map("Side.TButton", background=[("pressed", PANEL), ("active", PANEL)],
               bordercolor=[("active", PANEL)], foreground=[("active", TEXT)])
        st.configure("SideSel.TButton", background=ACCENT, foreground=ON_ACCENT, bordercolor=ACCENT,
                     borderwidth=0, padding=(16, 11), relief="flat", anchor="w", font=(fam, 11, "bold"),
                     focusthickness=0)
        st.map("SideSel.TButton", background=[("pressed", ACCENT_DARK), ("active", ACCENT_HOVER)],
               bordercolor=[("active", ACCENT_HOVER)], foreground=[("active", ON_ACCENT)])
        st.configure("App.TButton", background=BTN, foreground=TEXT, bordercolor=BTN, borderwidth=0,
                     padding=(14, 9), relief="flat", anchor="w", font=(fam, 10), focusthickness=0)
        st.map("App.TButton", background=[("pressed", ACCENT_DARK), ("active", BTN_HOVER)],
               bordercolor=[("active", BTN_HOVER)], foreground=[("pressed", ON_ACCENT)])
        self.serif = next((f for f in ("Playfair Display", "Georgia", "Cambria", "Times New Roman", "DejaVu Serif")
                           if f in fams), fam)
        self.ui_font = fam
        # кнопки
        st.configure("TButton", background=BTN, foreground=TEXT, bordercolor=BTN, borderwidth=0,
                     padding=(14, 8), relief="flat", focusthickness=0)
        st.map("TButton", background=[("disabled", PANEL), ("pressed", ACCENT_DARK), ("active", BTN_HOVER)],
               foreground=[("disabled", DIM)], bordercolor=[("active", BTN_HOVER)])
        st.configure("Accent.TButton", background=ACCENT, foreground=ON_ACCENT, bordercolor=ACCENT,
                     font=(fam, 10, "bold"))
        st.map("Accent.TButton", background=[("disabled", ACCENT_OFF), ("pressed", ACCENT_DARK),
                                             ("active", ACCENT_HOVER)],
               foreground=[("disabled", "#9DB2BE")], bordercolor=[("active", ACCENT_HOVER)])
        # поля
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(w, fieldbackground=FIELD, foreground=TEXT, bordercolor=BORDER, padding=(8, 6),
                         arrowcolor=TEXT, insertcolor=TEXT, relief="flat", background=BTN, arrowsize=14)
            st.map(w, background=[("active", BTN_HOVER), ("pressed", ACCENT_DARK)],
                   bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
                   fieldbackground=[("disabled", PANEL), ("readonly", FIELD)],
                   foreground=[("disabled", DIM)],
                   selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])
        self._check_imgs = []

        def box(fill, border, ticked):
            im = tk.PhotoImage(width=26, height=18)   # справа прозрачный отступ до текста
            im.put(border, to=(0, 0, 18, 18))
            im.put(fill, to=(1, 1, 17, 17))
            if ticked:
                pts = [(4, 9), (5, 10), (6, 11), (7, 12), (8, 11), (9, 10), (10, 9), (11, 8), (12, 7), (13, 6)]
                for x, y in pts:
                    im.put(ON_ACCENT, to=(x, y, x + 2, y + 2))
            self._check_imgs.append(im)
            return im

        off, on = box(FIELD, "#87634F", False), box(ACCENT, ACCENT, True)
        off_d, on_d = box(PANEL, BORDER, False), box(ACCENT_OFF, ACCENT_OFF, True)
        st.element_create("Pink.indicator", "image", off, ("disabled", "selected", on_d), ("disabled", off_d),
                          ("selected", on), ("active", off), sticky="")
        st.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Pink.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])
        st.configure("TCheckbutton", background=BG, foreground=TEXT, padding=(2, 4), focusthickness=0)
        st.map("TCheckbutton", background=[("active", BG)], foreground=[("disabled", DIM)])
        st.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=FIELD, borderwidth=0,
                     thickness=8, lightcolor=ACCENT, darkcolor=ACCENT)
        st.configure("Vertical.TScrollbar", background=BTN, troughcolor=BG, bordercolor=BG, arrowcolor=TEXT,
                     relief="flat", gripcount=0, width=12)
        st.map("Vertical.TScrollbar", background=[("active", BTN_HOVER)])
        st.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT, rowheight=30,
                     borderwidth=0, bordercolor=BORDER)
        st.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", ON_ACCENT)])
        st.configure("Treeview.Heading", background=PANEL, foreground=GREY, relief="flat", padding=(8, 7),
                     font=(fam, 10, "bold"))
        st.map("Treeview.Heading", background=[("active", BTN)])

    # ------------------------------------------------------------ общий каркас

    def _build_ui(self):
        self.side = tk.Frame(self, bg=SIDEBAR, width=250)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        main = ttk.Frame(self)
        main.pack(side="left", fill="both", expand=True)
        self.nb = ttk.Notebook(main)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.tab_up = ttk.Frame(self.nb, padding=22)
        self.tab_sel = ttk.Frame(self.nb, padding=22)
        self.tab_fin = ttk.Frame(self.nb, padding=22)
        self.tab_pf = ttk.Frame(self.nb, padding=22)
        self.tab_cl = ttk.Frame(self.nb, padding=22)
        self.tab_set = ttk.Frame(self.nb, padding=22)
        self.nb.add(self.tab_up, text="Загрузка")
        self.nb.add(self.tab_sel, text="Выбор клиента")
        self.nb.add(self.tab_fin, text="Выдача готовых")
        self.nb.add(self.tab_pf, text="Портфолио")
        self.nb.add(self.tab_cl, text="Клиенты")
        self.nb.add(self.tab_set, text="Настройки")
        self._build_sidebar()
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._build_upload(self.tab_up)
        self._build_select(self.tab_sel)
        self._build_final(self.tab_fin)
        self._build_portfolio(self.tab_pf)
        self._build_clients(self.tab_cl)
        self._build_settings(self._scrollable(self.tab_set))

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        row = ttk.Frame(bottom)
        row.pack(fill="x")
        self.pb = ttk.Progressbar(row, mode="determinate", maximum=1, value=0)
        self.pb.pack(side="left", fill="x", expand=True)
        self.stop_btn = ttk.Button(row, text="Остановить", state="disabled", command=self._stop)
        self.stop_btn.pack(side="left", padx=(8, 0))
        self.prog_var = tk.StringVar(value="Готов к работе")
        ttk.Label(bottom, textvariable=self.prog_var, foreground=GREY).pack(anchor="w", pady=(2, 4))
        self.log = ScrolledText(bottom, height=9, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="x")

    def _scrollable(self, parent):
        """Внутри вкладки делает прокручиваемую область (чтобы длинная вкладка не выталкивала журнал за экран)."""
        cv = tk.Canvas(parent, bg=BG, highlightthickness=0, height=200)
        sb = ttk.Scrollbar(parent, orient="vertical", command=cv.yview)
        inner = ttk.Frame(cv)
        win = cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        def wheel(e):
            if inner.winfo_reqheight() <= cv.winfo_height():
                return
            cv.yview_scroll(-1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1, "units")

        def on(_e):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                cv.bind_all(ev, wheel)

        def off(_e):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                cv.unbind_all(ev)

        cv.bind("<Enter>", on)
        cv.bind("<Leave>", off)
        return inner

    # ------------------------------------------------------------ левая панель

    def _photo(self, png):
        """PNG-байты -> картинка для кнопки (или None)."""
        if not png:
            return None
        try:
            img = tk.PhotoImage(data=base64.b64encode(png).decode("ascii"))
        except tk.TclError:
            return None
        self._imgs.append(img)
        return img

    def _build_sidebar(self):
        self._imgs = []
        side = self.side
        brand = tk.Label(side, text=" Photo Gallery", bg=SIDEBAR, fg=TEXT, font=(self.serif, 18),
                         anchor="w", compound="left")
        if getattr(self, "_icon64", None):
            self._brand_img = self._icon64.subsample(2, 2)      # 32 px
            brand.configure(image=self._brand_img)
        brand.pack(fill="x", padx=16, pady=(20, 0))
        tk.Label(side, text="галереи выбора фото", bg=SIDEBAR, fg=GREY, font=(self.ui_font, 9),
                 anchor="w").pack(fill="x", padx=18, pady=(0, 18))
        self.nav = {}
        items = ((self.tab_up, "Загрузка", "upload"), (self.tab_sel, "Выбор клиента", "select"),
                 (self.tab_fin, "Выдача готовых", "gift"), (self.tab_pf, "Портфолио", "portfolio"),
                 (self.tab_cl, "Клиенты", "clients"),
                 (self.tab_set, "Настройки", "settings"))
        for tab, title, kind in items:
            norm = self._photo(symbol_png(kind, TEXT))
            sel = self._photo(symbol_png(kind, ON_ACCENT))
            b = ttk.Button(side, text="  " + title, style="Side.TButton", compound="left",
                           command=lambda t=tab: self.nb.select(t))
            if norm:
                b.configure(image=norm)
            b.pack(fill="x", padx=10, pady=1)
            self.nav[str(tab)] = (b, norm, sel)

        tk.Frame(side, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(18, 10))
        tk.Label(side, text="ПРОГРАММЫ", bg=SIDEBAR, fg=GREY, font=(self.ui_font, 8, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(0, 6))
        self.app_btns = {}
        self._app_imgs = {}
        fallback = self._photo(symbol_png("photo", TEXT, 24))
        for key, label in (("photoshop", "Открыть Photoshop"), ("lightroom", "Открыть Lightroom")):
            b = ttk.Button(side, text="  " + label, style="App.TButton", compound="left",
                           command=lambda k=key: self._open_app(k))
            if fallback:
                b.configure(image=fallback)
            b.pack(fill="x", padx=10, pady=3)
            self.app_btns[key] = b
        self._fallback_icon = fallback
        self._build_usage(side)
        self._sync_nav()
        self._load_app_icons()

    # ------------------------------------------------------------ индикатор облака

    def _build_usage(self, side):
        st = ttk.Style(self)
        for name, color in (("Ok", ACCENT), ("Warn", "#E8B04A"), ("Bad", "#E5735F")):
            st.configure(f"Cloud{name}.Horizontal.TProgressbar", background=color, troughcolor=FIELD,
                         borderwidth=0, thickness=8, lightcolor=color, darkcolor=color)
        box = tk.Frame(side, bg=SIDEBAR, cursor="hand2")
        box.pack(side="bottom", fill="x", padx=18, pady=(0, 16))
        head = tk.Label(box, text="ОБЛАКО", bg=SIDEBAR, fg=GREY, font=(self.ui_font, 8, "bold"), anchor="w")
        head.pack(fill="x")
        self.usage_bar = ttk.Progressbar(box, mode="determinate", maximum=100, value=0,
                                         style="CloudOk.Horizontal.TProgressbar")
        self.usage_bar.pack(fill="x", pady=(5, 4))
        self.usage_var = tk.StringVar(value="нажми, чтобы узнать")
        self.usage_lbl = tk.Label(box, textvariable=self.usage_var, bg=SIDEBAR, fg=TEXT,
                                  font=(self.ui_font, 9), anchor="w", justify="left")
        self.usage_lbl.pack(fill="x")
        for w in (box, head, self.usage_bar, self.usage_lbl):
            w.bind("<Button-1>", lambda e: self.refresh_usage(manual=True))
        self.usage_busy = False

    def refresh_usage(self, manual=False):
        if self.usage_busy:
            return
        if not cloud_ready(self.cfg):
            self.usage_var.set("облако не настроено")
            return
        self.usage_busy = True
        self.usage_var.set("считаю...")
        cfg = dict(self.cfg)

        def run():
            try:
                self.q.put(("usage", op_cloud_usage(cfg), manual))
            except Exception as e:  # noqa: BLE001
                self.q.put(("usage", str(e), manual))

        threading.Thread(target=run, daemon=True).start()

    def _on_usage(self, res, manual):
        self.usage_busy = False
        if isinstance(res, str):
            self.usage_var.set("не удалось узнать")
            if manual:
                self._log(res)
            return
        limit = int(self.cfg.get("cloud_limit_gb") or 10) * 1024 ** 3
        pct = res["bytes"] * 100 / limit
        self.usage_bar.configure(value=min(pct, 100), style=(
            "CloudBad.Horizontal.TProgressbar" if pct >= 95 else
            "CloudWarn.Horizontal.TProgressbar" if pct >= 80 else "CloudOk.Horizontal.TProgressbar"))
        self.usage_var.set(f"{fmt_size(res['bytes'])} из {fmt_size(limit)} ({pct:.0f}%)\nсвободно {fmt_size(max(limit - res['bytes'], 0))}")
        if manual:
            names = {e.get("slug"): n for n, e in self.reg.items()}
            top = sorted(res["by"].items(), key=lambda kv: -kv[1])[:6]
            self._log(f"Облако: занято {fmt_size(res['bytes'])}, файлов {res['files']}. Больше всего: " +
                      ", ".join(f"{names.get(k, k)} {fmt_size(v)}" for k, v in top))
        if pct >= 95:
            self._log("ВНИМАНИЕ: облако почти заполнено. Закрой ненужных клиентов на вкладке «Клиенты».")

    def _sync_nav(self):
        try:
            current = self.nb.select()
        except tk.TclError:
            return
        for tab, (b, norm, sel) in self.nav.items():
            on = tab == str(current)
            b.configure(style="SideSel.TButton" if on else "Side.TButton")
            img = sel if on else norm
            if img:
                b.configure(image=img)

    def _load_app_icons(self):
        """Настоящие значки программ достаём в фоне (первый раз это занимает пару секунд)."""
        self._icons_q = queue.Queue()
        cfg = dict(self.cfg)

        def work():
            for key in APPS:
                path = resolve_app(cfg, key)
                self._icons_q.put((key, app_icon_png(path) if path else None))

        threading.Thread(target=work, daemon=True).start()
        self._icons_left = len(APPS)
        self.after(300, self._apply_app_icons)

    def _apply_app_icons(self):
        try:
            while True:
                key, png = self._icons_q.get_nowait()
                self._icons_left -= 1
                img = self._photo(png)
                if img:
                    self._app_imgs[key] = img
                    self.app_btns[key].configure(image=img)
                elif self._fallback_icon:
                    self.app_btns[key].configure(image=self._fallback_icon)
        except queue.Empty:
            pass
        if self._icons_left > 0:
            self.after(300, self._apply_app_icons)

    def _open_app(self, key):
        title = APPS[key]["title"]
        path = resolve_app(self.cfg, key)
        if not path:
            if not messagebox.askyesno(
                    "Photo Gallery", f"Не удалось найти {title} автоматически.\n\nУказать путь к программе вручную?",
                    parent=self):
                return
            path = self._pick_app(key)
            if not path:
                return
        try:
            launch_app(path)
            self._log(f"Открываю {title}: {path}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Photo Gallery", f"Не получилось запустить {title}:\n{e}", parent=self)

    def _pick_app(self, key):
        """Диалог выбора программы; путь сохраняется в настройках. Возвращает путь или ''."""
        title = APPS[key]["title"]
        if sys.platform.startswith("win"):
            types = [("Программы", "*.exe"), ("Все файлы", "*.*")]
        else:
            types = [("Все файлы", "*")]
        path = filedialog.askopenfilename(title=f"Укажите {title}", filetypes=types, parent=self)
        if not path and sys.platform == "darwin":
            path = filedialog.askdirectory(title=f"Укажите приложение {title} (.app)", parent=self)
        if not path:
            return ""
        self.cfg[APPS[key]["cfg"]] = path
        save_config(self.cfg)
        var = self.set_vars.get(APPS[key]["cfg"])
        if var is not None:
            var.set(path)
        self._load_app_icons()
        return path

    def _browse_app(self, key):
        self._pick_app(key)

    def _btn(self, parent, text, cmd, accent=False, **grid):
        b = ttk.Button(parent, text=text, command=cmd, style="Accent.TButton" if accent else "TButton")
        if grid:
            b.grid(**grid)
        self.action_buttons.append(b)
        return b

    # ------------------------------------------------------------ вкладка «Загрузка»

    def _build_upload(self, f):
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Клиент (латиницей, например anna-2026):").grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        self.name_cb = ttk.Combobox(f, textvariable=self.name_var, values=[])
        self.name_cb.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6)
        self.name_cb.bind("<<ComboboxSelected>>", lambda e: self._load_entry_form())
        self.name_cb.bind("<Return>", lambda e: self._load_entry_form())

        ttk.Label(f, text="Папка с фото на компьютере:").grid(row=1, column=0, sticky="w", pady=4)
        self.folder_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.folder_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="Выбрать...", command=self._browse_folder).grid(row=1, column=2)

        pf = ttk.LabelFrame(f, text=" Параметры клиента ", padding=10)
        pf.grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        pf.columnconfigure(1, weight=1)
        ttk.Label(pf, text="Что загружать:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value=MODE_LABELS[MODE_ORIGINAL])
        self.mode_cb = ttk.Combobox(pf, textvariable=self.mode_var, state="readonly",
                                    values=list(MODE_LABELS.values()))
        self.mode_cb.grid(row=0, column=1, sticky="ew", padx=6, pady=3)
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._update_mode_ui())
        ttk.Label(pf, text="Водяной знак на копиях:").grid(row=1, column=0, sticky="w")
        self.wm_var = tk.StringVar()
        self.wm_entry = ttk.Entry(pf, textvariable=self.wm_var)
        self.wm_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=3)
        ttk.Label(pf, text="Макс. фото на выбор (0 = без лимита):").grid(row=2, column=0, sticky="w")
        self.max_var = tk.StringVar(value="0")
        ttk.Spinbox(pf, from_=0, to=9999, width=8, textvariable=self.max_var).grid(
            row=2, column=1, sticky="w", padx=6, pady=3)
        self.suffix_var = tk.BooleanVar(value=True)
        self.suffix_cb = ttk.Checkbutton(
            pf, text="Случайный суффикс в ссылке (рекомендуется: адрес нельзя угадать)",
            variable=self.suffix_var)
        self.suffix_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        for i in range(4):
            bf.columnconfigure(i, weight=1, uniform="b")
        self._btn(bf, "1. Создать превью", self.on_thumbs, row=0, column=0, sticky="ew", padx=3, ipady=6)
        self._btn(bf, "2. Загрузить в облако", self.on_upload, row=0, column=1, sticky="ew", padx=3, ipady=6)
        self._btn(bf, "3. Страница и ссылка", self.on_page, row=0, column=2, sticky="ew", padx=3, ipady=6)
        self._btn(bf, "Всё сразу  (1 → 2 → 3)", self.on_all, accent=True,
                  row=0, column=3, sticky="ew", padx=3, ipady=6)
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="1 делает уменьшенные копии на компьютере. 2 загружает фото в облако "
                       "(после обрыва продолжит с того же места). 3 публикует страницу, копирует "
                       "ссылку и показывает её ниже.").grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 8))

        lf = ttk.LabelFrame(f, text=" Ссылка для клиента ", padding=10)
        lf.grid(row=5, column=0, columnspan=3, sticky="ew")
        lf.columnconfigure(0, weight=1)
        self.link_var = tk.StringVar()
        ttk.Entry(lf, textvariable=self.link_var, state="readonly").grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Button(lf, text="Копировать ссылку", command=self.copy_link).grid(row=1, column=0, sticky="w")
        ttk.Button(lf, text="Копировать сообщение клиенту", command=self.copy_message).grid(
            row=1, column=1, padx=6)
        ttk.Button(lf, text="Открыть в браузере", command=self.open_link).grid(row=1, column=2)
        self.info_var = tk.StringVar()
        ttk.Label(f, textvariable=self.info_var, foreground=GREY).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._update_mode_ui()

    def _mode_key(self):
        return MODE_VIEW if self.mode_var.get() == MODE_LABELS[MODE_VIEW] else MODE_ORIGINAL

    def _update_mode_ui(self):
        self.wm_entry.configure(state="normal" if self._mode_key() == MODE_VIEW else "disabled")

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Папка с фото клиента")
        if d:
            self.folder_var.set(d)

    def _load_entry_form(self):
        name = self.name_var.get().strip().lower()
        entry = self.reg.get(name)
        if entry:
            self.folder_var.set(entry["src"])
            self.mode_var.set(MODE_LABELS[entry["mode"]])
            self.wm_var.set(entry.get("watermark", ""))
            self.max_var.set(str(entry.get("max", 0)))
            self.mode_cb.configure(state="disabled" if entry.get("published") else "readonly")
            self.suffix_cb.configure(state="disabled")
            if entry.get("published") and cloud_ready(self.cfg):
                self.link_var.set(link_for(self.cfg, entry))
                self.info_var.set(f"Страница опубликована {entry['published']}. Создан {entry['created']}.")
            else:
                self.link_var.set("")
                self.info_var.set("Страница ещё не опубликована.")
        else:
            self.mode_cb.configure(state="readonly")
            self.suffix_cb.configure(state="normal")
            self.link_var.set("")
            self.info_var.set("Новый клиент." if name else "")
            if not self.max_var.get():
                self.max_var.set(str(self.cfg.get("max_select", 0)))
        self._update_mode_ui()

    def _entry_from_form(self):
        name = check_name(self.name_var.get())
        folder = self.folder_var.get().strip().strip('"')
        if not folder:
            raise AppError("Выбери папку с фото.")
        if not Path(folder).is_dir():
            raise AppError(f"Папка не найдена: {folder}")
        try:
            mx = int(self.max_var.get() or 0)
        except ValueError:
            raise AppError("Максимум фото на выбор должен быть числом.")
        mode, wm = self._mode_key(), self.wm_var.get().strip()
        entry = self.reg.get(name)
        if entry is None:
            entry = new_entry(name, folder, mode, mx, wm if mode == MODE_VIEW else "",
                              plain=not self.suffix_var.get())
            self.reg[name] = entry
        else:
            entry.update(src=folder, mode=mode, max=mx, watermark=wm if mode == MODE_VIEW else "")
        save_registry(self.reg)
        self._refresh_clients()
        return name, entry

    def _guard(self, fn):
        """Вызывает fn(), показывая AppError окном."""
        if self.busy:
            return
        try:
            fn()
        except AppError as e:
            messagebox.showerror("Photo Gallery", str(e), parent=self)

    def _need_cloud(self):
        if not cloud_ready(self.cfg):
            self.nb.select(self.tab_set)
            raise AppError("Сначала заполни и сохрани настройки облака (вкладка «Настройки»).")

    def on_thumbs(self):
        def go():
            name, entry = self._entry_from_form()
            cfg, e = dict(self.cfg), dict(entry)
            self._start("Создание превью", lambda ctx: op_thumbs(ctx, cfg, e))
        self._guard(go)

    def on_upload(self):
        def go():
            self._need_cloud()
            name, entry = self._entry_from_form()
            cfg, e = dict(self.cfg), dict(entry)
            self._start("Загрузка в облако", lambda ctx: op_upload(ctx, cfg, e))
        self._guard(go)

    def on_page(self):
        def go():
            self._need_cloud()
            name, entry = self._entry_from_form()
            cfg, e = dict(self.cfg), dict(entry)
            self._start("Публикация страницы", lambda ctx: op_page(ctx, cfg, e, name),
                        on_done=lambda link: self._after_publish(name, link))
        self._guard(go)

    def on_all(self):
        def go():
            self._need_cloud()
            name, entry = self._entry_from_form()
            cfg, e = dict(self.cfg), dict(entry)
            self._start("Всё сразу", lambda ctx: op_all(ctx, cfg, e, name),
                        on_done=lambda link: self._after_publish(name, link))
        self._guard(go)

    def _after_publish(self, name, link):
        if name in self.reg:
            self.reg[name]["published"] = now_str()
            save_registry(self.reg)
        self._refresh_clients()
        if self.name_var.get().strip().lower() == name:
            self.link_var.set(link)
            self.info_var.set(f"Страница опубликована {self.reg[name]['published']}.")
            self.mode_cb.configure(state="disabled")
        self._to_clipboard(link)
        self._log(f"ССЫЛКА ДЛЯ КЛИЕНТА (уже в буфере обмена): {link}")
        self._log("Открой её сам, сделай тестовый выбор и проверь, что он пришёл "
                  + ("(вкладка «Выбор клиента»)." if self._worker_on() else "в Telegram."))

    def _to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()

    def copy_link(self):
        link = self.link_var.get()
        if link:
            self._to_clipboard(link)
            self._log("Ссылка скопирована.")
        else:
            messagebox.showinfo("Photo Gallery", "Ссылки пока нет: сначала опубликуй страницу.", parent=self)

    def copy_message(self):
        link = self.link_var.get()
        if not link:
            messagebox.showinfo("Photo Gallery", "Ссылки пока нет: сначала опубликуй страницу.", parent=self)
            return
        self._to_clipboard(self.cfg.get("message", DEFAULT_MESSAGE).replace("{link}", link))
        self._log("Сообщение клиенту скопировано: вставь его в мессенджер или письмо.")

    def open_link(self):
        link = self.link_var.get()
        if link:
            webbrowser.open(link)

    # ------------------------------------------------------------ вкладка «Выбор клиента»

    def _build_select(self, f):
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Клиент:").grid(row=0, column=0, sticky="w")
        self.sel_client_var = tk.StringVar()
        self.sel_cb = ttk.Combobox(f, textvariable=self.sel_client_var, state="readonly", values=[])
        self.sel_cb.grid(row=0, column=1, sticky="ew", padx=6)
        self.sel_cb.bind("<<ComboboxSelected>>", lambda e: self._on_sel_client())
        ttk.Button(f, text="Вставить из буфера", command=self.paste_mail).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(f, text="Очистить", command=self.clear_mail).grid(row=0, column=3)

        inf = ttk.LabelFrame(f, text=" Выборы, пришедшие через Worker ", padding=8)
        inf.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        inf.columnconfigure(0, weight=1)
        self.inbox_var = tk.StringVar()
        self.inbox_cb = ttk.Combobox(inf, textvariable=self.inbox_var, state="readonly", values=[])
        self.inbox_cb.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(inf, text="Загрузить выбор", command=self._load_inbox_choice).grid(row=0, column=1, padx=3)
        self._btn(inf, "Проверить новые выборы", self.check_inbox_now, row=0, column=2, padx=3)
        self.inbox_info = tk.StringVar(value="Worker не подключён: выбор можно вставить из Telegram (ниже).")
        ttk.Label(inf, textvariable=self.inbox_info, foreground=GREY, wraplength=820, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        ttk.Label(f, text="Текст сообщения с выбором клиента (вставь целиком):", foreground=GREY).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(10, 2))
        self.mail = ScrolledText(f, height=10, font=("Consolas", 10), undo=True)
        self.mail.grid(row=3, column=0, columnspan=4, sticky="nsew")
        f.rowconfigure(3, weight=1)
        self.mail.bind("<<Paste>>", lambda e: self.after(150, self._parse_mail))
        self.mail.bind("<KeyRelease>", lambda e: self._schedule_parse())
        self._parse_job = None

        self.parse_var = tk.StringVar(value="Вставь сообщение: приложение найдёт клиента и список фото.")
        ttk.Label(f, textvariable=self.parse_var, wraplength=820, justify="left").grid(
            row=4, column=0, columnspan=4, sticky="w", pady=8)

        ttk.Label(f, text="Скопировать в папку:").grid(row=5, column=0, sticky="w")
        self.sel_out_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.sel_out_var).grid(row=5, column=1, columnspan=2, sticky="ew", padx=6)
        ttk.Button(f, text="Выбрать...", command=self._browse_out).grid(row=5, column=3)
        self.prefer_local_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Брать фото с компьютера, если они там есть (быстрее, полный размер)",
                        variable=self.prefer_local_var).grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.open_after_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Открыть папку после копирования",
                        variable=self.open_after_var).grid(row=7, column=0, columnspan=4, sticky="w")
        bf = ttk.Frame(f)
        bf.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        for i in range(3):
            bf.columnconfigure(i, weight=1, uniform="s")
        self._btn(bf, "Разобрать сообщение", self._parse_mail, row=0, column=0, sticky="ew", padx=3, ipady=6)
        self._btn(bf, "Скачать выбранные фото", self.on_download, accent=True,
                  row=0, column=1, sticky="ew", padx=3, ipady=6)
        self._btn(bf, "Открыть папку", self.open_out, row=0, column=2, sticky="ew", padx=3, ipady=6)

    # ---- выборы из облака (Worker)

    def _worker_on(self):
        return bool((self.cfg.get("worker_url") or "").strip())

    def check_inbox_now(self):
        def go():
            self._need_cloud()
            entries = {n: dict(e) for n, e in self.reg.items() if e.get("published")}
            if not entries:
                raise AppError("Пока нет опубликованных клиентов.")
            cfg = dict(self.cfg)
            self._start("Проверка новых выборов", lambda ctx: op_check_inbox(ctx, cfg, entries),
                        on_done=lambda r: self._on_inbox(r, manual=True))
        self._guard(go)

    def _auto_check(self):
        """Раз в несколько минут тихо ищет новые выборы, пока приложение открыто."""
        try:
            if cloud_ready(self.cfg) and self._worker_on() and not self.checking:
                entries = {n: dict(e) for n, e in self.reg.items() if e.get("published")}
                handled = list(self.pf.get("handled", []))
                if entries:
                    self.checking = True
                    cfg = dict(self.cfg)

                    def run():
                        try:
                            ctx = Ctx(lambda _m: None, threading.Event())
                            self.q.put(("inbox", op_check_inbox(ctx, cfg, entries)))
                            self.q.put(("reviews", op_check_reviews(ctx, cfg, handled)))
                        except Exception as e:  # noqa: BLE001
                            file_log(f"auto-check: {e}")
                        finally:
                            self.checking = False

                    threading.Thread(target=run, daemon=True).start()
        finally:
            self.after(AUTO_CHECK_MS, self._auto_check)

    def _on_inbox(self, res, manual=False):
        before = {i["key"] for items in self.inbox.values() for i in items}
        for name, r in res.items():
            if name not in self.reg:
                continue
            self.stats[name] = dict(r.get("stats") or {}, submissions=r.get("submissions", 0))
            self.inbox.pop(name, None)
            if r.get("new"):
                self.inbox[name] = r["new"]
        fresh = [(n, i) for n, items in self.inbox.items() for i in items if i["key"] not in before]
        for n, i in fresh:
            self._log(f"НОВЫЙ ВЫБОР: {n}, {i['client'] or 'клиент'}, {i['count']} фото. "
                      "Вкладка «Выбор клиента».")
        if manual and not self.inbox:
            self._log("Новых выборов нет.")
        self._refresh_inbox_ui()
        self._refresh_clients()
        if fresh and self.loaded is None and not self.mail.get("1.0", "end").strip():
            self._load_inbox_choice()       # поле пустое: сразу подставляем свежий выбор

    def _refresh_inbox_ui(self):
        items = sorted(((i["t"], n, i) for n, lst in self.inbox.items() for i in lst), reverse=True)
        labels, self.inbox_map = [], {}
        for _t, n, i in items:
            label = f"{n}  |  {fmt_iso(i['t'])}  |  {i['client'] or '?'}  |  {i['count']} фото"
            labels.append(label)
            self.inbox_map[label] = (n, i)
        self.inbox_cb.configure(values=labels)
        if self.inbox_var.get() not in self.inbox_map:
            self.inbox_var.set(labels[0] if labels else "")
        total = len(labels)
        self.nb.tab(self.tab_sel, text="Выбор клиента" + (f" ({total})" if total else ""))
        self.title(APP_TITLE + (f"  -  новых выборов: {total}" if total else ""))
        if total:
            self.inbox_info.set(f"Новых выборов: {total}. Выбери в списке и нажми «Загрузить выбор».")
        elif self._worker_on():
            self.inbox_info.set("Новых выборов нет. Приложение проверяет облако само раз в несколько минут.")
        else:
            self.inbox_info.set("Worker не подключён: выбор можно вставить из Telegram (ниже).")

    def _load_inbox_choice(self):
        label = self.inbox_var.get()
        if label not in self.inbox_map:
            messagebox.showinfo("Photo Gallery", "Новых выборов нет. Нажми «Проверить новые выборы».", parent=self)
            return
        name, it = self.inbox_map[label]
        self.mail.delete("1.0", "end")
        self.mail.insert("1.0", it["text"])
        self.last_clip = it["text"]
        self.sel_client_var.set(name)
        self._on_sel_client()
        self.loaded = (name, it["key"], it["text"].strip())
        self._parse_mail()

    def _mark_loaded_done(self):
        """Выбор из облака обработан: больше не показываем его как новый."""
        if not self.loaded:
            return
        name, key, text = self.loaded
        if self.mail.get("1.0", "end").strip() != text:
            return
        e = self.reg.get(name)
        if e is not None:
            e["seen"] = (list(e.get("seen") or []) + [key])[-500:]
            save_registry(self.reg)
            items = [i for i in self.inbox.get(name, []) if i["key"] != key]
            if items:
                self.inbox[name] = items
            else:
                self.inbox.pop(name, None)
        self.loaded = None
        self._refresh_inbox_ui()

    def _browse_out(self):
        d = filedialog.askdirectory(title="Куда копировать выбранные фото")
        if d:
            self.sel_out_var.set(d)

    def _on_sel_client(self):
        name = self.sel_client_var.get()
        if name:
            self.sel_out_var.set(str(Path(self.cfg.get("out_root") or DEFAULT_CONFIG["out_root"]) / name))

    def paste_mail(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showinfo("Photo Gallery", "В буфере обмена нет текста.", parent=self)
            return
        self.mail.delete("1.0", "end")
        self.mail.insert("1.0", text)
        self.last_clip = text
        self.loaded = None
        self._parse_mail()

    def clear_mail(self):
        self.mail.delete("1.0", "end")
        self.parsed = None
        self.loaded = None
        self.parse_var.set("Вставь сообщение: приложение найдёт клиента и список фото.")

    def _schedule_parse(self):
        if self._parse_job:
            self.after_cancel(self._parse_job)
        self._parse_job = self.after(500, self._parse_mail)

    def _parse_mail(self):
        text = self.mail.get("1.0", "end")
        if not text.strip():
            self.parsed = None
            return None
        info = parse_email(text)
        self.parsed = info
        if info["gallery"] in self.reg:
            self.sel_client_var.set(info["gallery"])
            self._on_sel_client()
        elif not self.sel_client_var.get() and len(self.reg) == 1:
            self.sel_client_var.set(next(iter(self.reg)))
            self._on_sel_client()
        parts = []
        if info["client"]:
            parts.append(f"Клиент в письме: {info['client']}")
        if info["gallery"]:
            known = "найдена" if info["gallery"] in self.reg else "НЕ найдена в списке"
            parts.append(f"галерея: {info['gallery']} ({known})")
        parts.append(f"фото в списке: {len(info['names'])}")
        if info.get("services"):
            cnt = {k: sum(1 for v in info["services"].values() if v == k) for k in SERVICES}
            parts.append("услуги: " + ", ".join(f"{SERVICES[k].lower()} {v}" for k, v in cnt.items() if v))
        if info.get("services") and any(parse_price(self.cfg.get("price_" + k)) > 0 for k in SERVICES):
            cnt = {k: sum(1 for v in info["services"].values() if v == k) for k in SERVICES}
            r = calc_total(cnt, pricing(self.cfg))
            cur = str(self.cfg.get("currency") or "").strip()
            txt = f"сумма по текущим ценам: {r['total']:g} {cur}".strip()
            if r["pct"]:
                txt += f" (скидка {r['pct']:g}%)"
            if info.get("client_total") is not None and abs(info["client_total"] - r["total"]) > 0.01:
                txt += f"; клиент видел {info['client_total']:g} (цены или скидки менялись после публикации)"
            parts.append(txt)
        if info.get("comments"):
            parts.append(f"комментариев к фото: {len(info['comments'])}")
        if info["declared"] is not None and info["declared"] != len(info["names"]):
            parts.append(f"в письме указано {info['declared']}: возможно, скопировано не всё письмо")
        name = self.sel_client_var.get()
        entry = self.reg.get(name)
        if entry:
            state = load_state(entry)
            if state:
                unknown = [n for n in info["names"] if n not in set(state["rels"])]
                if unknown:
                    parts.append(f"нет в этой галерее: {len(unknown)} (например {unknown[0]})")
        if info["rejected"]:
            parts.append(f"пропущено подозрительных имён: {len(info['rejected'])}")
        if not info["names"]:
            parts.append("ВНИМАНИЕ: имён фото не найдено")
        self.parse_var.set(" • ".join(parts))
        return info

    def on_download(self):
        def go():
            info = self._parse_mail()
            if not info or not info["names"]:
                raise AppError("Сначала вставь текст письма с выбором клиента.")
            name = self.sel_client_var.get()
            entry = self.reg.get(name)
            if not entry:
                raise AppError("Выбери клиента в списке сверху.")
            out = self.sel_out_var.get().strip()
            if not out:
                raise AppError("Укажи папку, куда копировать фото.")
            prefer = self.prefer_local_var.get()
            if not (prefer and Path(entry["src"]).is_dir()):
                self._need_cloud()
            cfg, e, names = dict(self.cfg), dict(entry), list(info["names"])
            comments = dict(info.get("comments") or {})
            services = dict(info.get("services") or {})
            self._start(f"Копирование выбранных фото ({name})",
                        lambda ctx: op_download(ctx, cfg, e, names, out, prefer, comments, services),
                        on_done=self._after_download)
        self._guard(go)

    def _after_download(self, res):
        self._log(f"Готово: {res['ok']} из {res['total']} фото -> {res['out']}")
        if not res["missing"]:
            self._mark_loaded_done()
        if res["missing"]:
            shown = ", ".join(res["missing"][:10])
            more = "" if len(res["missing"]) <= 10 else f" и ещё {len(res['missing']) - 10}"
            messagebox.showwarning("Photo Gallery", f"Не найдено файлов: {len(res['missing'])}\n{shown}{more}",
                                   parent=self)
        if self.open_after_var.get():
            open_path(res["out"])

    def open_out(self):
        out = self.sel_out_var.get().strip()
        if out and Path(out).is_dir():
            open_path(out)
        else:
            messagebox.showinfo("Photo Gallery", "Папки ещё нет: сначала скачай фото.", parent=self)

    def _on_tab_changed(self, _event=None):
        """Открыл вкладку «Выбор клиента»: если в буфере письмо, подхватываем его сами."""
        self._sync_nav()
        if self.nb.select() != str(self.tab_sel):
            return
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return
        if "Файлы:" in clip and clip != self.last_clip:
            self.last_clip = clip
            self.mail.delete("1.0", "end")
            self.mail.insert("1.0", clip)
            self._parse_mail()
            self._log("Письмо с выбором найдено в буфере обмена и вставлено.")

    # ------------------------------------------------------------ вкладка «Выдача готовых»

    def _build_final(self, f):
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Клиент:").grid(row=0, column=0, sticky="w", pady=4)
        self.fin_client_var = tk.StringVar()
        self.fin_cb = ttk.Combobox(f, textvariable=self.fin_client_var, state="readonly", values=[])
        self.fin_cb.grid(row=0, column=1, columnspan=2, sticky="ew", padx=6)
        self.fin_cb.bind("<<ComboboxSelected>>", lambda e: self._on_fin_client())
        ttk.Label(f, text="Папка с готовыми (отретушированными) фото:").grid(row=1, column=0, sticky="w", pady=4)
        self.fin_folder_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.fin_folder_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="Выбрать...", command=self._browse_final).grid(row=1, column=2)
        self.fin_zip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Добавить кнопку «Скачать всё одним архивом» (собирается ZIP: нужно место "
                                "на диске, загрузка дольше)", variable=self.fin_zip_var).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        bf.columnconfigure(0, weight=1)
        self._btn(bf, "Загрузить и создать страницу выдачи", self.on_final, accent=True,
                  row=0, column=0, sticky="ew", padx=3, ipady=8)
        lf = ttk.LabelFrame(f, text=" Ссылка на готовые фото ", padding=10)
        lf.grid(row=4, column=0, columnspan=3, sticky="ew")
        lf.columnconfigure(0, weight=1)
        self.fin_link_var = tk.StringVar()
        ttk.Entry(lf, textvariable=self.fin_link_var, state="readonly").grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Button(lf, text="Копировать ссылку", command=self.fin_copy_link).grid(row=1, column=0, sticky="w")
        ttk.Button(lf, text="Копировать сообщение клиенту", command=self.fin_copy_message).grid(
            row=1, column=1, padx=6)
        ttk.Button(lf, text="Открыть в браузере", command=self.fin_open).grid(row=1, column=2)
        self.fin_info = tk.StringVar()
        ttk.Label(f, textvariable=self.fin_info, foreground=GREY).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="Когда ретушь готова: выбери клиента и папку с готовыми фото. Приложение загрузит их "
                       "в облако, соберёт архив и создаст отдельную страницу, где клиент скачивает всё одной "
                       "кнопкой или по одному фото. Ссылка на неё не связана со ссылкой на выбор. "
                       "При повторном запуске грузится только изменившееся, а удалённые из папки фото "
                       "убираются со страницы. «Закрыть клиента» удаляет и выдачу.").grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _browse_final(self):
        d = filedialog.askdirectory(title="Папка с готовыми фото")
        if d:
            self.fin_folder_var.set(d)

    def _on_fin_client(self):
        name = self.fin_client_var.get()
        e = self.reg.get(name)
        if not e:
            return
        fin = e.get("final") or {}
        self.fin_folder_var.set(fin.get("src", ""))
        self.fin_zip_var.set(bool(fin.get("zip", True)))
        if fin and cloud_ready(self.cfg):
            self.fin_link_var.set(delivery_link(self.cfg, e))
            self.fin_info.set(f"Страница выдачи опубликована {fin.get('published', '')}, фото: {fin.get('count', '?')}.")
        else:
            self.fin_link_var.set("")
            self.fin_info.set("Выдача для этого клиента ещё не создавалась.")

    def on_final(self):
        def go():
            self._need_cloud()
            name = self.fin_client_var.get().strip()
            entry = self.reg.get(name)
            if not entry:
                raise AppError("Выбери клиента в списке.")
            folder = self.fin_folder_var.get().strip().strip('"')
            if not folder or not Path(folder).is_dir():
                raise AppError("Выбери папку с готовыми фото.")
            zipit = self.fin_zip_var.get()
            cfg, e = dict(self.cfg), dict(entry)
            self._start(f"Выдача готовых фото ({name})",
                        lambda ctx: op_delivery(ctx, cfg, e, name, folder, zipit),
                        on_done=lambda r: self._after_final(name, folder, zipit, r))
        self._guard(go)

    def _after_final(self, name, folder, zipit, res):
        e = self.reg.get(name)
        if e is not None:
            e["final"] = {"src": folder, "zip": zipit, "published": now_str(), "count": res["count"]}
            save_registry(self.reg)
        self._refresh_clients()
        if self.fin_client_var.get() == name:
            self.fin_link_var.set(res["link"])
            self.fin_info.set(f"Страница выдачи опубликована {now_str()}, фото: {res['count']}.")
        self._to_clipboard(res["link"])
        self._log(f"ССЫЛКА НА ГОТОВЫЕ ФОТО (уже в буфере обмена): {res['link']}")

    def fin_copy_link(self):
        link = self.fin_link_var.get()
        if link:
            self._to_clipboard(link)
            self._log("Ссылка на выдачу скопирована.")
        else:
            messagebox.showinfo("Photo Gallery", "Ссылки пока нет: сначала создай страницу выдачи.", parent=self)

    def fin_copy_message(self):
        link = self.fin_link_var.get()
        if not link:
            messagebox.showinfo("Photo Gallery", "Ссылки пока нет: сначала создай страницу выдачи.", parent=self)
            return
        self._to_clipboard(DEFAULT_FINAL_MESSAGE.replace("{link}", link))
        self._log("Сообщение клиенту скопировано.")

    def fin_open(self):
        link = self.fin_link_var.get()
        if link:
            webbrowser.open(link)

    # ------------------------------------------------------------ вкладка «Портфолио»

    def _build_portfolio(self, f):
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)
        sw = ttk.Frame(f)
        sw.grid(row=0, column=0, sticky="w", pady=(0, 12))
        self.pf_sw = {}
        for key, label in (("works", "Работы"), ("reviews", "Отзывы")):
            b = ttk.Button(sw, text=label, width=14, command=lambda k=key: self._pf_show(k))
            b.pack(side="left", padx=(0, 6), ipady=3)
            self.pf_sw[key] = b
        body = ttk.Frame(f)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.pf_works = ttk.Frame(body)
        self.pf_reviews = ttk.Frame(body)
        for fr in (self.pf_works, self.pf_reviews):
            fr.grid(row=0, column=0, sticky="nsew")
        self._build_pf_works(self.pf_works)
        self._build_pf_reviews(self.pf_reviews)
        self._pf_show("works")

    def _pf_show(self, key):
        (self.pf_works if key == "works" else self.pf_reviews).tkraise()
        for k, b in self.pf_sw.items():
            b.configure(style="Accent.TButton" if k == key else "TButton")

    def _build_pf_works(self, f):
        f.columnconfigure(1, weight=1)
        self.pf_vars = {}
        rows = (("src", "Папка с лучшими работами:"), ("title", "Заголовок страницы:"))
        r = 0
        for key, label in rows:
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            self.pf_vars[key] = tk.StringVar()
            ttk.Entry(f, textvariable=self.pf_vars[key]).grid(row=r, column=1, sticky="ew", padx=6)
            if key == "src":
                ttk.Button(f, text="Выбрать...", command=self._pf_browse).grid(row=r, column=2)
            r += 1
        ttk.Label(f, text="Обо мне:").grid(row=r, column=0, sticky="nw", pady=4)
        self.pf_about = tk.Text(f, height=4, wrap="word")
        self.pf_about.grid(row=r, column=1, columnspan=2, sticky="ew", padx=6, pady=3)
        r += 1
        for key, label, hint in (("instagram", "Instagram:", "@ник или ссылка"),
                                 ("telegram", "Telegram:", "@ник или ссылка"),
                                 ("site", "Сайт:", "адрес сайта"),
                                 ("email", "Email:", "для кнопки «Написать»"),
                                 ("watermark", "Водяной знак:", "текст поверх фото (необязательно)")):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            self.pf_vars[key] = tk.StringVar()
            ttk.Entry(f, textvariable=self.pf_vars[key]).grid(row=r, column=1, sticky="ew", padx=6)
            ttk.Label(f, text=hint, foreground=GREY).grid(row=r, column=2, sticky="w")
            r += 1
        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        bf.columnconfigure(0, weight=1)
        self._btn(bf, "Опубликовать портфолио", self.on_pf_publish, accent=True,
                  row=0, column=0, sticky="ew", padx=3, ipady=8)
        r += 1
        lf = ttk.LabelFrame(f, text=" Ссылка на портфолио ", padding=10)
        lf.grid(row=r, column=0, columnspan=3, sticky="ew")
        lf.columnconfigure(0, weight=1)
        self.pf_link_var = tk.StringVar()
        ttk.Entry(lf, textvariable=self.pf_link_var, state="readonly").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(lf, text="Копировать ссылку", command=self.pf_copy_link).grid(row=1, column=0, sticky="w")
        ttk.Button(lf, text="Открыть в браузере", command=self.pf_open).grid(row=1, column=1, padx=6)
        r += 1
        self.pf_info = tk.StringVar()
        ttk.Label(f, textvariable=self.pf_info, foreground=GREY, wraplength=820, justify="left").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(8, 0))
        r += 1
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="На сайт попадают копии для просмотра (оригиналы не загружаются), по желанию с водяным "
                       "знаком. После публикации на страницах клиентов («Обновить страницу») и на странице выдачи "
                       "появляется ссылка «Портфолио и отзывы».").grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _build_pf_reviews(self, f):
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        lf = ttk.Frame(f)
        lf.grid(row=0, column=0, sticky="nsew")
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        cols = ("status", "author", "rating", "text")
        self.rv_tree = ttk.Treeview(lf, columns=cols, show="headings", height=10, selectmode="browse")
        for c, t, w in (("status", "Статус", 150), ("author", "Автор", 150), ("rating", "Оценка", 70),
                        ("text", "Отзыв", 420)):
            self.rv_tree.heading(c, text=t)
            self.rv_tree.column(c, width=w, anchor="w", stretch=(c == "text"))
        self.rv_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.rv_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.rv_tree.configure(yscrollcommand=sb.set)
        self.rv_tree.tag_configure("new", foreground=ACCENT)
        self.rv_tree.bind("<Double-1>", lambda e: self.rv_edit())
        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(bf, text="Добавить отзыв...", command=self.rv_add).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(bf, text="Изменить...", command=self.rv_edit).grid(row=0, column=1, padx=6)
        ttk.Button(bf, text="Удалить", command=self.rv_delete).grid(row=0, column=2, padx=6)
        self._btn(bf, "Проверить новые отзывы", self.rv_check, row=0, column=3, padx=(18, 6))
        ttk.Button(bf, text="Принять", command=self.rv_accept).grid(row=0, column=4, padx=6)
        ttk.Button(bf, text="Отклонить", command=self.rv_reject).grid(row=0, column=5, padx=6)
        bf2 = ttk.Frame(f)
        bf2.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bf2.columnconfigure(0, weight=1)
        self._btn(bf2, "Обновить портфолио на сайте", self.on_pf_publish, accent=True,
                  row=0, column=0, sticky="ew", padx=3, ipady=6)
        self.rv_info = tk.StringVar()
        ttk.Label(f, textvariable=self.rv_info, foreground=GREY, wraplength=820, justify="left").grid(
            row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="Отзывы можно вписать самому (например, из переписки) или получать от клиентов: на странице "
                       "портфолио, открытой по ссылке из галереи клиента, есть кнопка «Оставить отзыв» (нужен "
                       "Worker, обновлённый до новой версии). Отзыв клиента сначала попадает сюда как «Новый»: "
                       "прочитай, при желании исправь и нажми «Принять». На сайте он появится после "
                       "«Обновить портфолио на сайте».").grid(row=4, column=0, sticky="w", pady=(6, 0))

    # --- данные формы

    def _pf_load_form(self):
        pf = self.pf
        for k, v in self.pf_vars.items():
            v.set(str(pf.get(k, "")))
        self.pf_about.delete("1.0", "end")
        self.pf_about.insert("1.0", pf.get("about", ""))
        if pf.get("published") and cloud_ready(self.cfg):
            self.pf_link_var.set(portfolio_link(self.cfg))
            self.pf_info.set(f"Опубликовано {pf['published']}, работ: {pf.get('count', '?')}.")
        else:
            self.pf_link_var.set("")
            self.pf_info.set("Портфолио ещё не опубликовано.")
        self._rv_refresh()

    def _pf_save_form(self):
        for k, v in self.pf_vars.items():
            self.pf[k] = v.get().strip().strip('"') if k == "src" else v.get().strip()
        self.pf["about"] = self.pf_about.get("1.0", "end").strip()
        save_portfolio(self.pf)

    def _pf_browse(self):
        d = filedialog.askdirectory(title="Папка с лучшими работами")
        if d:
            self.pf_vars["src"].set(d)

    # --- публикация

    def on_pf_publish(self):
        def go():
            self._need_cloud()
            self._pf_save_form()
            src = self.pf.get("src", "")
            if not src or not Path(src).is_dir():
                raise AppError("Выбери папку с лучшими работами (вкладка «Работы»).")
            cfg, pf = dict(self.cfg), json.loads(json.dumps(self.pf))
            self._start("Портфолио", lambda ctx: op_portfolio(ctx, cfg, pf), on_done=self._after_pf)
        self._guard(go)

    def _after_pf(self, res):
        first = not self.pf.get("published")
        self.pf["published"] = now_str()
        self.pf["count"] = res["count"]
        save_portfolio(self.pf)
        self.pf_link_var.set(res["link"])
        self.pf_info.set(f"Опубликовано {self.pf['published']}, работ: {res['count']}.")
        self._to_clipboard(res["link"])
        self._log(f"ССЫЛКА НА ПОРТФОЛИО (уже в буфере обмена): {res['link']}")
        if first:
            self._log("Чтобы у клиентов появилась кнопка «Портфолио и отзывы», нажми «Обновить страницу» "
                      "на вкладке «Клиенты» (для нужных клиентов).")

    def pf_copy_link(self):
        link = self.pf_link_var.get()
        if link:
            self._to_clipboard(link)
            self._log("Ссылка на портфолио скопирована.")
        else:
            messagebox.showinfo("Photo Gallery", "Ссылки пока нет: сначала опубликуй портфолио.", parent=self)

    def pf_open(self):
        link = self.pf_link_var.get()
        if link:
            webbrowser.open(link)

    # --- отзывы

    def _rv_refresh(self):
        tree = self.rv_tree
        tree.delete(*tree.get_children())
        for i, p in enumerate(self.pf_pending):
            who = p["author"] or "—"
            cl = next((n for n, e in self.reg.items() if e.get("slug") == p.get("slug")), "")
            if cl:
                who += f" ({cl})"
            tree.insert("", "end", iid=f"p{i}", tags=("new",),
                        values=("Новый", who, "★" * p["rating"], " ".join(p["text"].split())))
        for r in self.pf.get("reviews", []):
            tree.insert("", "end", iid="r" + str(r.get("id")),
                        values=("На сайте", r.get("author", ""), "★" * int(r.get("rating") or 5),
                                " ".join(str(r.get("text", "")).split())))
        n = len(self.pf_pending)
        self.rv_info.set(f"Ждут решения: {n}. На сайте: {len(self.pf.get('reviews', []))}." if n or self.pf.get("reviews")
                         else "Отзывов пока нет.")

    def _rv_selected(self):
        sel = self.rv_tree.selection()
        if not sel:
            messagebox.showinfo("Photo Gallery", "Выбери отзыв в списке.", parent=self)
            return None
        iid = sel[0]
        if iid.startswith("p"):
            return "new", self.pf_pending[int(iid[1:])]
        for r in self.pf["reviews"]:
            if str(r.get("id")) == iid[1:]:
                return "pub", r
        return None

    def _rv_dialog(self, init):
        """Окно редактирования отзыва. Возвращает dict или None."""
        top = tk.Toplevel(self)
        top.title("Отзыв")
        top.configure(bg=BG)
        top.transient(self)
        top.resizable(False, False)
        frm = ttk.Frame(top, padding=18)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        name_v = tk.StringVar(value=init.get("author", ""))
        rate_v = tk.StringVar(value=str(init.get("rating", 5)))
        date_v = tk.StringVar(value=init.get("date", datetime.now().strftime("%d.%m.%Y")))
        ttk.Label(frm, text="Имя:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=name_v, width=44).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Label(frm, text="Оценка:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(frm, textvariable=rate_v, values=["5", "4", "3", "2", "1"], state="readonly",
                     width=6).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(frm, text="Дата:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frm, textvariable=date_v, width=16).grid(row=2, column=1, sticky="w", padx=8)
        ttk.Label(frm, text="Отзыв:").grid(row=3, column=0, sticky="nw", pady=4)
        txt = tk.Text(frm, height=8, width=52, wrap="word")
        txt.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        txt.insert("1.0", init.get("text", ""))
        result = {}

        def ok():
            t = txt.get("1.0", "end").strip()
            if len(t) < 3:
                messagebox.showinfo("Photo Gallery", "Впиши текст отзыва.", parent=top)
                return
            result.update(author=name_v.get().strip(), rating=int(rate_v.get() or 5), date=date_v.get().strip(),
                          text=t[:1500])
            top.destroy()

        bf = ttk.Frame(frm)
        bf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(bf, text="Отмена", command=top.destroy).pack(side="left", padx=6)
        ttk.Button(bf, text="Сохранить", style="Accent.TButton", command=ok).pack(side="left")
        top.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - top.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - top.winfo_height()) // 3
        top.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        top.bind("<Escape>", lambda e: top.destroy())
        try:
            top.grab_set()
        except tk.TclError:
            pass
        txt.focus_set()
        self.wait_window(top)
        return result or None

    def _rv_changed(self):
        save_portfolio(self.pf)
        self._rv_refresh()
        if self.pf.get("published"):
            self.rv_info.set(self.rv_info.get() + "  Чтобы изменения появились на сайте, нажми "
                                                  "«Обновить портфолио на сайте».")

    def rv_add(self):
        r = self._rv_dialog({})
        if r:
            r["id"] = secrets.token_hex(4)
            self.pf["reviews"].insert(0, r)
            self._rv_changed()

    def rv_edit(self):
        cur = self._rv_selected()
        if not cur:
            return
        kind, rec = cur
        init = dict(rec)
        if kind == "new":
            init["date"] = self._rv_date(rec.get("t"))
        r = self._rv_dialog(init)
        if not r:
            return
        if kind == "pub":
            rec.update(r)
            self._rv_changed()
        else:
            self._rv_take(rec, r)

    @staticmethod
    def _rv_date(t):
        try:
            return datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone().strftime("%d.%m.%Y")
        except (ValueError, TypeError, OSError):
            return datetime.now().strftime("%d.%m.%Y")

    def _rv_take(self, pend, data=None):
        """Принять отзыв клиента (можно с правками): в список на сайте, ключ из облака убираем."""
        data = data or {"author": pend["author"], "rating": pend["rating"], "text": pend["text"],
                        "date": self._rv_date(pend.get("t"))}
        data["id"] = secrets.token_hex(4)
        self.pf["reviews"].insert(0, data)
        self._rv_drop_pending(pend)

    def _rv_drop_pending(self, pend):
        self.pf["handled"].append(pend["key"])
        self.pf["handled"] = self.pf["handled"][-500:]
        self.pf_pending = [p for p in self.pf_pending if p["key"] != pend["key"]]
        cfg = dict(self.cfg)
        threading.Thread(target=delete_cloud_keys, args=(cfg, [pend["key"]]), daemon=True).start()
        self._rv_changed()

    def rv_accept(self):
        cur = self._rv_selected()
        if not cur:
            return
        if cur[0] != "new":
            messagebox.showinfo("Photo Gallery", "Этот отзыв уже на сайте. «Принять» нужно для новых отзывов "
                                                 "от клиентов.", parent=self)
            return
        self._rv_take(cur[1])

    def rv_reject(self):
        cur = self._rv_selected()
        if not cur:
            return
        if cur[0] != "new":
            messagebox.showinfo("Photo Gallery", "Чтобы убрать отзыв с сайта, нажми «Удалить».", parent=self)
            return
        if messagebox.askyesno("Photo Gallery", "Отклонить этот отзыв? Он будет удалён.", parent=self):
            self._rv_drop_pending(cur[1])

    def rv_delete(self):
        cur = self._rv_selected()
        if not cur:
            return
        kind, rec = cur
        if kind == "new":
            self.rv_reject()
            return
        if messagebox.askyesno("Photo Gallery", "Удалить этот отзыв?", parent=self):
            self.pf["reviews"] = [r for r in self.pf["reviews"] if r is not rec]
            self._rv_changed()

    def rv_check(self):
        def go():
            self._need_cloud()
            cfg, handled = dict(self.cfg), list(self.pf.get("handled", []))
            self._start("Проверка отзывов", lambda ctx: op_check_reviews(ctx, cfg, handled),
                        on_done=lambda r: self._on_reviews(r, manual=True))
        self._guard(go)

    def _on_reviews(self, items, manual=False):
        known = {p["key"] for p in self.pf_pending}
        handled = set(self.pf.get("handled", []))
        items = [i for i in items if i["key"] not in handled]
        fresh = [i for i in items if i["key"] not in known]
        self.pf_pending = items
        self._rv_refresh()
        if fresh:
            self._log(f"Новых отзывов от клиентов: {len(fresh)}. Вкладка «Портфолио» → «Отзывы».")
        elif manual:
            self._log("Новых отзывов нет.")

    # ------------------------------------------------------------ вкладка «Клиенты»

    def _build_clients(self, f):
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        cols = ("name", "created", "age", "mode", "state", "activity")
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse", height=12)
        for c, t, w in (("name", "Клиент", 100), ("created", "Создан", 135), ("age", "Дн.", 40),
                        ("mode", "Что в облаке", 105), ("state", "Статус", 200),
                        ("activity", "Активность клиента", 290)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("old", background="#5E4330", foreground="#F0CF9B")
        self.tree.bind("<Double-1>", lambda e: self.c_edit())
        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        items = [("Открыть в «Загрузке»", self.c_edit), ("Копировать ссылку", self.c_copy),
                 ("Открыть ссылку", self.c_open), ("Обновить страницу", self.c_republish),
                 ("Размер и стоимость", self.c_stats), ("Просмотры и выбор", self.c_views),
                 ("Папка с фото", self.c_folder), ("Закрыть клиента", self.c_close),
                 ("Убрать из списка", self.c_forget)]
        for i, (t, cmd) in enumerate(items):
            self._btn(bf, t, cmd, row=i // 4, column=i % 4, sticky="ew", padx=3, pady=3, ipady=4)
        for i in range(4):
            bf.columnconfigure(i, weight=1, uniform="c")
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="«Закрыть клиента» удаляет его фото и страницу из облака (ссылка перестанет работать). "
                       "Оранжевым отмечены клиенты, у которых прошёл срок хранения из настроек: "
                       "их стоит закрыть, чтобы не платить за хранение.").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _refresh_clients(self):
        names = sorted(self.reg)
        self.name_cb.configure(values=names)
        self.sel_cb.configure(values=names)
        self.fin_cb.configure(values=names)
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        days = int(self.cfg.get("expire_days") or 0)
        for n in names:
            e = self.reg[n]
            age = age_days(e)
            old = days > 0 and age >= days
            state = f"опубликовано {e['published'][:10]}" if e.get("published") else "не опубликовано"
            if e.get("final"):
                state += " • выдача"
            self.tree.insert("", "end", iid=n, tags=("old",) if old else (),
                             values=(n, e["created"], age, "оригиналы" if e["mode"] == MODE_ORIGINAL
                                     else "копии", state, self._activity(n)))
        if sel and sel[0] in self.reg:
            self.tree.selection_set(sel[0])

    def _activity(self, name):
        st = self.stats.get(name)
        if not st:
            return ""
        parts = []
        if st.get("views"):
            parts.append(f"открывал {st['views']}× (последний {fmt_iso(st.get('last'))})")
        if st.get("submissions"):
            parts.append(f"выборов отправлено: {st['submissions']}")
        elif st.get("selected"):
            parts.append(f"отметил {st['selected']}")
        return ", ".join(parts)

    def c_views(self):
        def go():
            name = self._sel_client()
            if not name:
                return
            self._need_cloud()
            if not self.reg[name].get("published"):
                raise AppError("Страница этого клиента ещё не опубликована.")
            cfg, e = dict(self.cfg), dict(self.reg[name])
            self._start(f"Просмотры {name}", lambda ctx: op_check_inbox(ctx, cfg, {name: e}),
                        on_done=lambda r: (self._on_inbox(r, manual=True), self._show_views(name)))
        self._guard(go)

    def _show_views(self, name):
        st = self.stats.get(name) or {}
        if not st.get("views") and not st.get("submissions"):
            extra = "" if self._worker_on() else "\n\nWorker не подключён (Настройки): без него статистики нет."
            messagebox.showinfo("Просмотры и выбор", f"Клиент «{name}» пока не открывал страницу "
                                f"(или страница опубликована до подключения Worker: нажми «Обновить "
                                f"страницу»).{extra}", parent=self)
            return
        lines = [f"Клиент «{name}»", "",
                 f"Открытий страницы: {st.get('views', 0)}",
                 f"Первое открытие: {fmt_iso(st.get('first'))}",
                 f"Последняя активность: {fmt_iso(st.get('last'))}"]
        if "selected" in st:
            lines.append(f"Отмечено при последнем визите: {st.get('selected', 0)}, "
                         f"комментариев: {st.get('comments', 0)}")
        lines.append(f"Отправленных выборов: {st.get('submissions', 0)}")
        new = len(self.inbox.get(name, []))
        if new:
            lines.append(f"Из них ещё не обработано: {new} (вкладка «Выбор клиента»)")
        messagebox.showinfo("Просмотры и выбор", "\n".join(lines), parent=self)

    def _sel_client(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Photo Gallery", "Выбери клиента в списке.", parent=self)
            return None
        return sel[0]

    def c_edit(self):
        name = self._sel_client()
        if name:
            self.name_var.set(name)
            self._load_entry_form()
            self.nb.select(self.tab_up)

    def c_copy(self):
        name = self._sel_client()
        if name and cloud_ready(self.cfg):
            self._to_clipboard(link_for(self.cfg, self.reg[name]))
            self._log(f"Ссылка клиента {name} скопирована.")

    def c_open(self):
        name = self._sel_client()
        if name and cloud_ready(self.cfg):
            webbrowser.open(link_for(self.cfg, self.reg[name]))

    def c_folder(self):
        name = self._sel_client()
        if name:
            p = Path(self.reg[name]["src"])
            if p.is_dir():
                open_path(p)
            else:
                messagebox.showinfo("Photo Gallery", f"Папки нет на компьютере:\n{p}", parent=self)

    def c_republish(self):
        def go():
            name = self._sel_client()
            if not name:
                return
            self._need_cloud()
            cfg, e = dict(self.cfg), dict(self.reg[name])
            self._start(f"Обновление страницы {name}", lambda ctx: op_page(ctx, cfg, e, name),
                        on_done=lambda link: self._after_publish(name, link))
        self._guard(go)

    def c_stats(self):
        def go():
            name = self._sel_client()
            if not name:
                return
            self._need_cloud()
            cfg, e = dict(self.cfg), dict(self.reg[name])
            self._start(f"Размер {name} в облаке", lambda ctx: op_stats(ctx, cfg, e),
                        on_done=lambda r: messagebox.showinfo(
                            "Размер в облаке",
                            f"Клиент «{name}»\nФайлов: {r['files']}\nРазмер: {fmt_size(r['bytes'])}\n"
                            f"Примерно ${r['cost']:.2f} в месяц "
                            f"(без учёта бесплатных 10 ГБ на аккаунт)", parent=self))
        self._guard(go)

    def c_close(self):
        def go():
            name = self._sel_client()
            if not name:
                return
            self._need_cloud()
            entry = self.reg[name]
            warn = ""
            if not Path(entry["src"]).is_dir():
                warn = ("\n\nВНИМАНИЕ: папки с оригиналами нет на компьютере. "
                        "После удаления фото будут потеряны.")
            ans = simpledialog.askstring(
                "Закрыть клиента",
                f"Все файлы клиента «{name}» будут удалены из облака безвозвратно "
                f"(корзины нет), ссылка перестанет работать. Файлы на компьютере не затрагиваются.{warn}"
                f"\n\nДля подтверждения введи имя клиента:", parent=self)
            if (ans or "").strip().lower() != name:
                return
            cfg, e = dict(self.cfg), dict(entry)
            self._start(f"Закрытие клиента {name}", lambda ctx: op_close(ctx, cfg, e),
                        on_done=lambda _r: self._forget(name))
        self._guard(go)

    def c_forget(self):
        name = self._sel_client()
        if name and messagebox.askyesno(
                "Убрать из списка",
                f"Убрать «{name}» из списка приложения?\nФайлы в облаке при этом НЕ удаляются "
                f"(и продолжают занимать место).", parent=self):
            self._forget(name)

    def _forget(self, name):
        self.reg.pop(name, None)
        self.stats.pop(name, None)
        self.inbox.pop(name, None)
        self._refresh_inbox_ui()
        save_registry(self.reg)
        self._refresh_clients()
        if self.name_var.get().strip().lower() == name:
            self.name_var.set("")
            self.folder_var.set("")
            self._load_entry_form()

    # ------------------------------------------------------------ вкладка «Настройки»

    SETTING_FIELDS = [
        ("account_id", "Cloudflare Account ID", "R2 → Overview, справа на странице", False),
        ("access_key_id", "R2 Access Key ID", "из токена R2 (Object Read & Write)", False),
        ("secret_access_key", "R2 Secret Access Key", "показывается один раз при создании токена", True),
        ("bucket", "Имя бакета", "например photos", False),
        ("public_url", "Публичный адрес бакета", "https://pub-xxxx.r2.dev или свой домен, без слеша в конце", False),
        ("telegram_token", "Telegram: токен бота", "от @BotFather, вида 123456:ABC...", True),
        ("telegram_chat_id", "Telegram: Chat ID", "ваш числовой ID (узнать у @userinfobot); сначала нажмите Start у бота", False),
        ("worker_url", "Worker: адрес (рекомендуется)", "https://имя.аккаунт.workers.dev (см. инструкцию)", False),
        ("title", "Заголовок страницы", "его видит клиент", False),
        ("max_select", "Макс. фото на выбор по умолчанию", "0 = без лимита", False),
        ("view_size", "Размер копий для просмотра, px", "для режима «Только копии для просмотра»", False),
        ("expire_days", "Напомнить закрыть клиента через, дней", "0 = не напоминать", False),
        ("cloud_limit_gb", "Лимит облака для индикатора, ГБ", "бесплатно в R2: 10", False),
        ("out_root", "Папка для выбранных фото", "внутри будут папки по именам клиентов", False),
        ("photoshop_path", "Путь к Photoshop", "пусто = найти автоматически", False),
        ("lightroom_path", "Путь к Lightroom", "пусто = найти автоматически", False),
    ]

    def _build_settings(self, f):
        f.columnconfigure(1, weight=1, minsize=300)
        self.set_vars = {}
        for r, (key, label, hint, secret) in enumerate(self.SETTING_FIELDS):
            ttk.Label(f, text=label + ":").grid(row=r, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            self.set_vars[key] = var
            ttk.Entry(f, textvariable=var, show="•" if secret else "").grid(
                row=r, column=1, sticky="ew", padx=6)
            if key == "out_root":
                ttk.Button(f, text="Выбрать...", command=self._browse_out_root).grid(row=r, column=2, sticky="w")
            elif key in ("photoshop_path", "lightroom_path"):
                af = ttk.Frame(f)
                af.grid(row=r, column=2, sticky="w")
                app_key = key[:-5]
                ttk.Button(af, text="Выбрать...", command=lambda k=app_key: self._browse_app(k)).pack(side="left")
                ttk.Label(af, text=hint, foreground=GREY).pack(side="left", padx=(8, 0))
            else:
                ttk.Label(f, text=hint, foreground=GREY, wraplength=330, justify="left").grid(
                    row=r, column=2, sticky="w")
        n = len(self.SETTING_FIELDS)
        pf_ = ttk.LabelFrame(f, text=" Цены, которые видит клиент на странице выбора (пусто = не показывать) ", padding=8)
        pf_.grid(row=n, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for c in (1, 3, 5):
            pf_.columnconfigure(c, weight=1, uniform="pr")
        for c, (key, label) in enumerate((("price_color", "Цветокоррекция:"), ("price_retouch", "Ретушь:"),
                                          ("price_comment", "Комментарий:"))):
            ttk.Label(pf_, text=label).grid(row=0, column=c * 2, sticky="w", padx=(0 if c == 0 else 14, 6))
            self.set_vars[key] = tk.StringVar()
            ttk.Entry(pf_, textvariable=self.set_vars[key]).grid(row=0, column=c * 2 + 1, sticky="ew")
        ttk.Label(pf_, text="Скидки (от N фото : %):").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.set_vars["discount_tiers"] = tk.StringVar()
        ttk.Entry(pf_, textvariable=self.set_vars["discount_tiers"]).grid(
            row=1, column=2, columnspan=2, sticky="ew", padx=(0, 6), pady=(8, 0))
        ttk.Label(pf_, text="Валюта:").grid(row=1, column=4, sticky="w", padx=(14, 6), pady=(8, 0))
        self.set_vars["currency"] = tk.StringVar()
        ttk.Entry(pf_, textvariable=self.set_vars["currency"], width=8).grid(row=1, column=5, sticky="w", pady=(8, 0))
        ttk.Label(pf_, foreground=GREY, wraplength=900, justify="left",
                  text="Цена: число из текста (5 € за фото = 5). Скидка по числу фото с платной услугой, действует на всю "
                       "сумму: «10:5, 20:10, 30:15» = от 10 фото −5%, от 20 −10%, от 30 −15%. Пусто = без скидок."
                  ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
        n += 1
        mf = ttk.LabelFrame(f, text=" Сообщение клиенту ({link} заменится ссылкой) ", padding=8)
        mf.grid(row=n, column=0, columnspan=3, sticky="ew", pady=8)
        mf.columnconfigure(0, weight=1)
        self.msg_text = tk.Text(mf, height=2, wrap="word")
        self.msg_text.grid(row=0, column=0, sticky="ew")
        bf = ttk.Frame(f)
        bf.grid(row=n + 1, column=0, columnspan=3, sticky="w")
        self._btn(bf, "Сохранить", self.save_settings, accent=True, row=0, column=0, padx=(0, 6), ipady=4)
        self._btn(bf, "Проверить подключение", self.test_connection, row=0, column=1, padx=6, ipady=4)
        self._btn(bf, "Проверить Telegram", self.test_telegram, row=0, column=2, padx=6, ipady=4)
        ttk.Button(bf, text="Открыть папку данных", command=lambda: open_path(DATA)).grid(
            row=0, column=3, padx=6, ipady=4)
        self._btn(bf, "Проверить Worker", self.test_worker, row=1, column=0, padx=(0, 6), pady=(6, 0), ipady=4)
        self._btn(bf, "Подготовить бакет для телефона", self.prepare_phone, row=2, column=0, columnspan=2, padx=(0, 6), pady=(6, 0), ipady=4)
        self._btn(bf, "Скопировать настройки для телефона", self.copy_phone_settings, row=2, column=2, columnspan=2, padx=6, pady=(6, 0), ipady=4)
        ttk.Button(bf, text="Скопировать код Worker", command=self.copy_worker_code).grid(
            row=1, column=1, padx=6, pady=(6, 0), ipady=4)
        ttk.Button(bf, text="Сохранить worker.js в файл", command=self.save_worker_file).grid(
            row=1, column=2, padx=6, pady=(6, 0), ipady=4)
        ttk.Label(f, foreground=GREY, wraplength=820, justify="left",
                  text="Ключи хранятся на этом компьютере в открытом виде (папка данных). "
                       "Журнал работы: gallery.log в той же папке.").grid(
            row=n + 2, column=0, columnspan=3, sticky="w", pady=(10, 0))

    def _browse_out_root(self):
        d = filedialog.askdirectory(title="Папка для выбранных фото")
        if d:
            self.set_vars["out_root"].set(d)

    def _load_settings_form(self):
        for key, var in self.set_vars.items():
            var.set(str(self.cfg.get(key, "")))
        self.msg_text.delete("1.0", "end")
        self.msg_text.insert("1.0", self.cfg.get("message", DEFAULT_MESSAGE))

    def _read_settings_form(self):
        new = dict(self.cfg)
        for key, var in self.set_vars.items():
            new[key] = var.get().strip()
        for key in ("max_select", "view_size", "expire_days", "cloud_limit_gb"):
            try:
                new[key] = int(new[key] or 0)
            except ValueError:
                raise AppError(f"Поле «{key}» должно быть числом.")
        if new["cloud_limit_gb"] <= 0:
            new["cloud_limit_gb"] = 10
        if new["view_size"] < 300:
            new["view_size"] = 1600
        new["public_url"] = new["public_url"].rstrip("/")
        new["worker_url"] = new.get("worker_url", "").rstrip("/")
        if new["worker_url"] and not new["worker_url"].startswith("https://"):
            raise AppError("Адрес Worker должен начинаться с https://")
        new["message"] = self.msg_text.get("1.0", "end").strip() or DEFAULT_MESSAGE
        return new

    def save_settings(self):
        try:
            self.cfg = self._read_settings_form()
        except AppError as e:
            messagebox.showerror("Photo Gallery", str(e), parent=self)
            return
        save_config(self.cfg)
        self._log("Настройки сохранены.")
        self.refresh_usage()
        self._load_app_icons()
        self._refresh_clients()
        self._load_entry_form()

    def test_telegram(self):
        def go():
            self.save_settings()
            cfg = dict(self.cfg)
            self._start("Проверка Telegram", lambda ctx: op_test_telegram(ctx, cfg),
                        on_done=lambda msg: messagebox.showinfo("Photo Gallery", msg, parent=self))
        self._guard(go)

    def test_worker(self):
        def go():
            self.save_settings()
            cfg = dict(self.cfg)
            self._start("Проверка Worker", lambda ctx: op_test_worker(ctx, cfg),
                        on_done=lambda msg: messagebox.showinfo("Photo Gallery", msg, parent=self))
        self._guard(go)

    def copy_phone_settings(self):
        def go():
            self.save_settings()
            self._need_cloud()
            self._to_clipboard(phone_settings_json(self.cfg))
            self._log("Настройки для телефона скопированы: вставь их в приложении «Съёмки» → Настройки.")
        self._guard(go)

    def prepare_phone(self):
        def go():
            self.save_settings()
            self._need_cloud()
            cfg = dict(self.cfg)
            self._start("Подготовка бакета для телефона", lambda ctx: op_prepare_phone(ctx, cfg),
                        on_done=lambda msg: messagebox.showinfo("Photo Gallery", msg, parent=self))
        self._guard(go)

    def copy_worker_code(self):
        self._to_clipboard(WORKER_SOURCE)
        self._log("Код Worker скопирован: вставь его в Cloudflare (Edit code) вместо всего, что там есть.")

    def save_worker_file(self):
        path = DATA / "worker.js"
        path.write_text(WORKER_SOURCE, encoding="utf-8")
        self._log(f"Код Worker сохранён: {path}")
        open_path(DATA)

    def test_connection(self):
        def go():
            self.save_settings()
            self._need_cloud()
            cfg = dict(self.cfg)
            self._start("Проверка подключения", lambda ctx: op_test(ctx, cfg),
                        on_done=lambda msg: messagebox.showinfo("Photo Gallery", msg, parent=self))
        self._guard(go)

    # ------------------------------------------------------------ фоновые задачи

    def _start(self, title, fn, on_done=None):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.task_cb = on_done
        self._set_busy(True)
        self._log(f"=== {title} ===")
        ctx = Ctx(self.q.put, self.cancel)

        def worker():
            try:
                self.q.put(("done", fn(ctx)))
            except Cancelled:
                self.q.put(("cancelled", None))
            except AppError as e:
                self.q.put(("error", str(e)))
            except Exception:  # noqa: BLE001
                self.q.put(("crash", traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def _set_busy(self, busy):
        for b in self.action_buttons:
            b.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")
        if not busy:
            self.pb.configure(value=0, maximum=1)

    def _stop(self):
        self.cancel.set()
        self.prog_var.set("Останавливаю...")

    def _poll(self):
        try:
            while True:
                self._handle(self.q.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _handle(self, msg):
        kind = msg[0]
        if kind == "log":
            self._log(msg[1])
        elif kind == "inbox":
            self._on_inbox(msg[1])
        elif kind == "reviews":
            self._on_reviews(msg[1])
        elif kind == "usage":
            self._on_usage(msg[1], msg[2])
        elif kind == "progress":
            _, label, done, total, bdone, btotal = msg
            self.pb.configure(maximum=max(total, 1), value=done)
            text = f"{label}: {done} из {total}"
            if btotal:
                text += f"  ({fmt_size(bdone)} из {fmt_size(btotal)})"
            self.prog_var.set(text)
        else:
            cb, self.task_cb = self.task_cb, None
            self.busy = False
            self._set_busy(False)
            if kind == "done":
                self.after(300, self.refresh_usage)
                self.prog_var.set("Готово")
                self._log("Готово.")
                if cb:
                    try:
                        cb(msg[1])
                    except Exception:  # noqa: BLE001
                        self._log(traceback.format_exc())
            elif kind == "cancelled":
                self.prog_var.set("Остановлено")
                self._log("Остановлено. Запусти операцию снова: работа продолжится с того же места.")
            elif kind == "error":
                self.prog_var.set("Ошибка")
                self._log("ОШИБКА: " + msg[1])
                messagebox.showerror("Photo Gallery", msg[1], parent=self)
            elif kind == "crash":
                self.prog_var.set("Ошибка")
                self._log(msg[1])
                last = msg[1].strip().splitlines()[-1]
                messagebox.showerror("Photo Gallery", f"Непредвиденная ошибка:\n{last}\n\n"
                                     f"Подробности в журнале: {LOG_PATH}", parent=self)

    def _log(self, msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        file_log(line)

    def _on_callback_error(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        self._log(text)
        messagebox.showerror("Photo Gallery", f"Ошибка в приложении:\n{val}\n\nЖурнал: {LOG_PATH}", parent=self)

    def _startup_checks(self):
        if not cloud_ready(self.cfg):
            self.nb.select(self.tab_set)
            self._log("Первый запуск: заполни настройки облака и нажми «Сохранить». "
                      "Где взять значения, написано в инструкции.")
            return
        self.refresh_usage()
        days = int(self.cfg.get("expire_days") or 0)
        if days > 0:
            old = [n for n, e in self.reg.items() if age_days(e) >= days]
            if old:
                self.nb.select(self.tab_cl)
                self._log(f"Срок хранения прошёл у клиентов: {', '.join(old)}")
                messagebox.showinfo("Photo Gallery",
                                    f"Эти клиенты хранятся в облаке дольше {days} дн.:\n\n" + "\n".join(old) +
                                    "\n\nЕсли они больше не нужны, закрой их на вкладке «Клиенты»: "
                                    "это освободит место в облаке.", parent=self)

    def _on_close(self):
        if self.busy and not messagebox.askyesno(
                "Photo Gallery", "Идёт операция. Выйти? Её можно будет продолжить позже.", parent=self):
            return
        self.destroy()
        os._exit(0)


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    App().mainloop()


if __name__ == "__main__":
    main()
