# src/clustering.py
import numpy as np
import re
from collections import Counter
from sklearn.metrics.pairwise import cosine_distances
from sklearn.metrics import silhouette_score
import hdbscan

from src.embeddings import get_embedding

# ---------- Вспомогательные функции ----------
def _get_word_set(text: str) -> set:
    """Извлекает множество знаменательных слов (нижний регистр, только буквы/цифры)."""
    words = re.findall(r'\b[a-zа-яё0-9]+\b', text.lower())
    return set(words)

def _jaccard(a: set, b: set) -> float:
    """Коэффициент Жаккара для двух множеств."""
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def _centroid_name(reasons: list[str], embeddings: np.ndarray) -> str:
    """Выбирает причину, ближайшую к центроиду кластера (по косинусной близости)."""
    if len(reasons) == 1:
        return reasons[0]
    centroid = np.mean(embeddings, axis=0)
    sims = np.dot(embeddings, centroid)
    best_idx = np.argmax(sims)
    return reasons[best_idx]

def _merge_close_clusters(
    groups: list[dict],
    embeddings: np.ndarray,
    threshold: float = 0.35
) -> list[dict]:
    """
    Объединяет не-шумовые кластеры, центроиды которых находятся на расстоянии < threshold.
    Возвращает новый список групп.
    """
    non_noise = [g for g in groups if not g['is_noise']]
    noise = [g for g in groups if g['is_noise']]
    if len(non_noise) <= 1:
        return groups

    # Вычисляем центроиды для не-шумовых кластеров
    centroids = []
    for g in non_noise:
        embs = [get_embedding(m) for m in g['members']]
        centroids.append(np.mean(embs, axis=0))
    centroids = np.array(centroids)

    n = len(centroids)
    merged = [False] * n
    new_groups = []
    for i in range(n):
        if merged[i]:
            continue
        group = non_noise[i].copy()
        for j in range(i + 1, n):
            if merged[j]:
                continue
            dist = 1 - np.dot(centroids[i], centroids[j])
            if dist < threshold:
                group['members'].extend(non_noise[j]['members'])
                group['size'] = len(group['members'])
                merged[j] = True
        if group['size'] > 1:
            embs = [get_embedding(m) for m in group['members']]
            group['name'] = _centroid_name(group['members'], np.array(embs))
        new_groups.append(group)
    new_groups.extend(noise)
    new_groups.sort(key=lambda g: g['size'], reverse=True)
    return new_groups

def _auto_alpha(
    reasons: list[str],
    embeddings: np.ndarray,
    word_sets: list[set],
    min_cluster_size: int,
    min_samples: int,
    cluster_selection_method: str
) -> float:
    """
    Перебирает α от 0 до 1 с шагом 0.1, выбирает значение, максимизирующее силуэт.
    Возвращает лучший α.
    """
    n = len(reasons)    
    cos_dist = np.zeros((n, n))
    overlap = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            cd = 1 - np.dot(embeddings[i], embeddings[j])
            ov = _jaccard(word_sets[i], word_sets[j])
            cos_dist[i, j] = cos_dist[j, i] = cd
            overlap[i, j] = overlap[j, i] = ov

    best_sil = -1.0
    best_alpha = 1.0
    for a in np.arange(0.0, 1.05, 0.1):
        D = cos_dist * (1 - a * overlap)
        clusterer = hdbscan.HDBSCAN(
            metric='precomputed',
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_method=cluster_selection_method
        )
        labels = clusterer.fit_predict(D)
        mask = labels != -1
        if mask.sum() >= 2 and len(set(labels[mask])) >= 2:
            sil = silhouette_score(D[mask][:, mask], labels[mask], metric='precomputed')
        else:
            sil = -1
        if sil > best_sil:
            best_sil = sil
            best_alpha = a
    return best_alpha

# ---------- Основная функция кластеризации ----------
def cluster_reasons(
    reasons: list[str],
    min_samples: int = 3,
    k_neighbors: int = 5,
    alpha: float | str = 'auto',
    verbose: bool = False
) -> list[dict]:
    """
    Кластеризация причин с помощью HDBSCAN и гибридной метрики.
    Параметры адаптируются под размер выборки.
    Возвращает список групп: {name, members, size, is_noise}.
    """
    # Фильтрация пустых строк
    reasons = [r for r in reasons if r and r.strip()]
    if not reasons:
        return []
    N = len(reasons)

    # Адаптивные параметры HDBSCAN (по результатам экспериментов)
    if N < 200:
        min_cluster_size = 2
        min_samples_hdb = 1
        cluster_selection_method = 'leaf'
    else:
        min_cluster_size = max(3, int(N * 0.05))
        min_samples_hdb = 2
        cluster_selection_method = 'eom'

    # Если количество причин меньше минимального размера кластера, не запускаем HDBSCAN
    if N < min_cluster_size:
        return [{"name": r, "members": [r], "size": 1, "is_noise": False} for r in reasons]

    # Для очень маленьких выборок не используем гибридную метрику (чисто косинусное)
    if alpha == 'auto' and N < 50:
        eff_alpha = 0.0
        if verbose:
            print(f"Маленькая выборка ({N} причин), чистая косинусная метрика (α=0)")
    else:
        if alpha == 'auto':
            # Получаем эмбеддинги и множества слов для авто-подбора α
            embeddings = np.array([get_embedding(r) for r in reasons])
            word_sets = [_get_word_set(r) for r in reasons]
            eff_alpha = _auto_alpha(
                reasons, embeddings, word_sets,
                min_cluster_size, min_samples_hdb, cluster_selection_method
            )
            if verbose:
                print(f"Авто-подбор α = {eff_alpha:.2f}")
        else:
            eff_alpha = float(alpha)

    # Вычисляем эмбеддинги и множества слов
    embeddings = np.array([get_embedding(r) for r in reasons])
    word_sets = [_get_word_set(r) for r in reasons]

    # Предвычисляем косинусные расстояния и overlap для гибридной метрики
    n = N
    cos_dist = np.zeros((n, n))
    overlap = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            cd = 1 - np.dot(embeddings[i], embeddings[j])
            ov = _jaccard(word_sets[i], word_sets[j])
            cos_dist[i, j] = cos_dist[j, i] = cd
            overlap[i, j] = overlap[j, i] = ov

    # Построение матрицы расстояний
    D = cos_dist * (1 - eff_alpha * overlap)

    # HDBSCAN
    try:
        clusterer = hdbscan.HDBSCAN(
            metric='precomputed',
            min_cluster_size=min_cluster_size,
            min_samples=min_samples_hdb,
            cluster_selection_method=cluster_selection_method
        )
        labels = clusterer.fit_predict(D)
    except ValueError as e:
        if "Invalid shape in axis 0: 0" in str(e):
            # Если HDBSCAN не может обработать, возвращаем каждую причину отдельно
            if verbose:
                print(f"Ошибка HDBSCAN: {e}. Возвращаем все причины как шум.")
            return [{"name": r, "members": [r], "size": 1, "is_noise": True} for r in reasons]
        else:
            raise

    # Группировка
    clusters = {}
    noise_indices = []
    for i, lbl in enumerate(labels):
        if lbl == -1:
            noise_indices.append(i)
        else:
            clusters.setdefault(lbl, []).append(i)

    # Формируем предварительный список групп
    groups = []
    for lbl, idxs in clusters.items():
        grp_reasons = [reasons[i] for i in idxs]
        grp_embs = embeddings[idxs]
        name = _centroid_name(grp_reasons, grp_embs)
        groups.append({
            "name": name,
            "members": grp_reasons,
            "size": len(grp_reasons),
            "is_noise": False,
        })
    for i in noise_indices:
        groups.append({
            "name": reasons[i],
            "members": [reasons[i]],
            "size": 1,
            "is_noise": True,
        })

    # объединение слишком близких кластеров
    groups = _merge_close_clusters(groups, embeddings, threshold=0.42)

    groups.sort(key=lambda g: g['size'], reverse=True)
    if verbose:
        n_clusters = sum(1 for g in groups if not g['is_noise'])
        n_noise = sum(1 for g in groups if g['is_noise'])
        print(f"Кластеризация: {n_clusters} кластеров, {n_noise} шумовых точек, α={eff_alpha:.2f}")
    return groups

# ---------- Оставшиеся функции (совместимость) ----------
def filter_reasons_by_aspect(reasons: list[str], aspect: str, max_distance: float = 0.55) -> list[str]:
    """Фильтрует причины по семантической близости к аспекту (без изменений)."""
    if not reasons:
        return []
    aspect_emb = np.array(get_embedding(aspect)).reshape(1, -1)
    filtered = []
    for reason in reasons:
        reason_emb = np.array(get_embedding(reason)).reshape(1, -1)
        dist = cosine_distances(aspect_emb, reason_emb)[0, 0]
        if dist < max_distance:
            filtered.append(reason)
    return filtered

def aggregate_deep_analysis(praised: list[str], criticized: list[str]) -> dict:
    """Агрегирует и кластеризует списки причин (без изменений)."""
    # Удаляем пустые строки перед агрегацией
    praised = [p for p in praised if p and p.strip()]
    criticized = [c for c in criticized if c and c.strip()]

    praised_counts = Counter(praised)
    criticized_counts = Counter(criticized)

    unique_praised = list(praised_counts.keys())
    unique_criticized = list(criticized_counts.keys())

    praised_clusters = cluster_reasons(unique_praised) if unique_praised else []
    criticized_clusters = cluster_reasons(unique_criticized) if unique_criticized else []

    def add_frequencies(clusters, counts):
        for group in clusters:
            group["total_frequency"] = sum(counts[m] for m in group["members"])
            group["members_with_freq"] = [{"reason": m, "count": counts[m]} for m in group["members"]]
        return clusters

    return {
        "praised_groups": add_frequencies(praised_clusters, praised_counts),
        "criticized_groups": add_frequencies(criticized_clusters, criticized_counts),
    }