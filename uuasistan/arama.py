"""Arama yöntemleri: BM25 (Türkçe kök bulmayla), yoğun (embedding), RRF birleştirme ve yeniden sıralama.

Yoğun arama ve yeniden sıralama `sentence-transformers` ister (Colab'da GPU ile çalıştırılır);
BM25 ve RRF yalnızca `rank-bm25` ve `snowballstemmer` ile yerelde çalışır.
"""
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

# Mevzuat metinlerinde ayırt ediciliği olmayan sık sözcükler
DURAK = set("""
ve veya ile ya da de ki bu şu o bir için gibi kadar göre olan olarak ise ancak her
mi mı mu mü ne nasıl nedir neden hangi kaç midir mıdır var yok olur olup
ben benim bana sen senin sana biz bizim
""".split())

KELIME = re.compile(r"[0-9a-zçğıöşüâîû]+")


def kucuk(metin: str) -> str:
    """Türkçe küçük harf: I -> ı, İ -> i (str.lower bunları yanlış çevirir)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


@lru_cache(maxsize=1)
def _kok_bulucu():
    import snowballstemmer
    return snowballstemmer.stemmer("turkish")


def tokenlar(metin: str, kok: str | None = "snowball") -> list:
    kelimeler = [k for k in KELIME.findall(kucuk(metin)) if k not in DURAK]
    if kok == "snowball":
        return _kok_bulucu().stemWords(kelimeler)
    if kok == "onek5":  # Türkçe IR'da bilinen basit yöntem: ilk 5 harf
        return [k[:5] for k in kelimeler]
    return kelimeler


def _en_iyi(skorlar: np.ndarray, k: int) -> list:
    return [int(i) for i in np.argsort(-skorlar, kind="stable")[:k]]


class BM25:
    def __init__(self, metinler: list, kok: str | None = "snowball"):
        self.kok = kok
        self.model = BM25Okapi([tokenlar(m, kok) for m in metinler])

    def ara(self, sorgu: str, k: int = 50) -> list:
        return _en_iyi(self.model.get_scores(tokenlar(sorgu, self.kok)), k)


@dataclass(frozen=True)
class YogunModel:
    ad: str
    sorgu_oneki: str = ""
    belge_oneki: str = ""
    sorgu_prompt_adi: str | None = None


_TALIMAT = "Instruct: Given a Turkish search query, retrieve relevant passages written in Turkish that best answer the query\nQuery: "

# Önekler model kartlarındaki kullanım talimatlarından alındı
YOGUN_MODELLER = {
    "bge-m3": YogunModel("BAAI/bge-m3"),
    "me5-large": YogunModel("intfloat/multilingual-e5-large", "query: ", "passage: "),
    "me5-large-instruct": YogunModel("intfloat/multilingual-e5-large-instruct", _TALIMAT),
    "me5-small": YogunModel("intfloat/multilingual-e5-small", "query: ", "passage: "),
    "turkish-e5-large": YogunModel("ytu-ce-cosmos/turkish-e5-large", _TALIMAT),
    "qwen3-emb-0.6b": YogunModel("Qwen/Qwen3-Embedding-0.6B", sorgu_prompt_adi="query"),
    # newmindai/TurkEmbed4Retrieval çıkarıldı: özel kodu güncel transformers ile uyumsuz,
    # Colab'da GPU'da device-side assert tetikleyip deneyin geri kalanını çökertiyor.
    "mursit-large-tr": YogunModel("newmindai/Mursit-Large-TR-Retrieval"),
}

YENIDEN_SIRALAYICILAR = {
    "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
    "modernbert-tr-reranker": "ytu-ce-cosmos/modernbert-tr-reranker",
}

MAKS_TOKEN = 512  # parçalar 1500 karakteri aşmıyor; başlıkla birlikte ~400-450 token


class Yogun:
    def __init__(self, metinler: list, model: YogunModel, cihaz: str | None = None, toplu: int = 16, yarim: bool = False):
        """yarim: fp16 (GPU belleğinin yarısı); dil modeliyle aynı GPU'yu paylaşırken."""
        from sentence_transformers import SentenceTransformer

        self.model = model
        self.st = SentenceTransformer(model.ad, device=cihaz)
        if yarim:
            self.st.half()
        self.st.max_seq_length = min(self.st.max_seq_length or MAKS_TOKEN, MAKS_TOKEN)
        self.belgeler = self.st.encode(
            [model.belge_oneki + m for m in metinler],
            batch_size=toplu, normalize_embeddings=True, convert_to_numpy=True,
        )

    def ara_toplu(self, sorgular: list, k: int = 50) -> list:
        ek = {"prompt_name": self.model.sorgu_prompt_adi} if self.model.sorgu_prompt_adi else {}
        q = self.st.encode(
            [self.model.sorgu_oneki + s for s in sorgular],
            normalize_embeddings=True, convert_to_numpy=True, **ek,
        )
        return [_en_iyi(self.belgeler @ v, k) for v in q]


def rrf(siralamalar: list, k: int = 60, derinlik: int = 50) -> list:
    """Reciprocal Rank Fusion: birden fazla sıralamayı skor ölçeğinden bağımsız birleştirir."""
    skor = {}
    for siralama in siralamalar:
        for r, i in enumerate(siralama):
            skor[i] = skor.get(i, 0.0) + 1.0 / (k + r + 1)
    return sorted(skor, key=lambda i: (-skor[i], i))[:derinlik]


class YenidenSiralayici:
    def __init__(self, ad: str, cihaz: str | None = None, yarim: bool = False):
        from sentence_transformers import CrossEncoder

        self.ce = CrossEncoder(ad, device=cihaz, max_length=MAKS_TOKEN)
        if yarim:
            self.ce.model.half()

    def sirala(self, sorgu: str, adaylar: list, metinler: list) -> list:
        skorlar = self.ce.predict([(sorgu, metinler[i]) for i in adaylar], batch_size=16)
        return [adaylar[j] for j in np.argsort(-np.asarray(skorlar), kind="stable")]
