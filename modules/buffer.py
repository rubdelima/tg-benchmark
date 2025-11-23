import ollama
from annoy import AnnoyIndex
from collections import OrderedDict

from schemas.task import Task, BaseTask

class VectorBuffer:
    def __init__(self, embedding_model="embeddinggemma", vector_dim=768, buffer_limit=5000, build_every=5):
        self.embedding_model = embedding_model
        self.vector_dim = vector_dim
        self.annoy = AnnoyIndex(vector_dim, 'angular')
        self.inmem_buffer: OrderedDict[int, Task] = OrderedDict() #type:ignore
        self.vector_map = {}  # {id: embedding}
        self._next_id = 0
        self.buffer_limit = buffer_limit
        self._mod_counter = 0   # Conta quantas modificações até rebuild
        self._build_every = build_every  # Rebuild após este nº de mudanças

    def _get_text_for_embedding(self, task: BaseTask):
        keywords_str = " ".join(task.keywords)
        return f"{task.definition} | {keywords_str} | {task.dod}"

    def _get_vector(self, task: BaseTask):
        text = self._get_text_for_embedding(task)
        vecs = ollama.embed(model=self.embedding_model, input=[text]) #type:ignore
        return vecs['embeddings'][0]

    def _evict_if_needed(self):
        while len(self.inmem_buffer) > self.buffer_limit:
            old_id, _ = self.inmem_buffer.popitem(last=False)
            self.vector_map.pop(old_id, None)
            self._mod_counter += 1

    def _rebuild_annoy(self):
        self.annoy = AnnoyIndex(self.vector_dim, 'angular')
        for idx, emb in self.vector_map.items():
            self.annoy.add_item(idx, emb)
        if len(self.vector_map) > 0:
            self.annoy.build(10)
        self._mod_counter = 0

    def create(self, task: Task):
        emb = self._get_vector(task)
        idx = self._next_id
        self.inmem_buffer[idx] = task
        self.vector_map[idx] = emb
        self._next_id += 1
        self._mod_counter += 1
        self._evict_if_needed()
        if self._mod_counter >= self._build_every:
            self._rebuild_annoy()
        return idx

    def read(self, idx):
        return self.inmem_buffer.get(idx, None)

    def update(self, idx, updated_task: Task):
        if idx not in self.inmem_buffer: return False
        emb = self._get_vector(updated_task)
        self.inmem_buffer[idx] = updated_task
        self.vector_map[idx] = emb
        self._mod_counter += 1
        if self._mod_counter >= self._build_every:
            self._rebuild_annoy()
        return True

    def delete(self, idx):
        if idx in self.inmem_buffer:
            self.inmem_buffer.pop(idx)
            self.vector_map.pop(idx, None)
            self._mod_counter += 1
            if self._mod_counter >= self._build_every:
                self._rebuild_annoy()
        return True

    def build(self):
        self._rebuild_annoy()

    def semantic_search(self, query_task: BaseTask, top_k=3):
        if len(self.vector_map) < 3:
            qvec = self._get_vector(query_task)
            matches = []
            for idx, emb in self.vector_map.items():
                score = sum(a*b for a,b in zip(qvec, emb))
                matches.append((score, idx))
            matches.sort(reverse=True)
            return [self.inmem_buffer[idx] for score, idx in matches[:top_k]]

        if self.annoy.get_n_items() == 0:
            self._rebuild_annoy()
        qvec = self._get_vector(query_task)
        idxs = self.annoy.get_nns_by_vector(qvec, top_k)
        return [self.inmem_buffer[idx] for idx in idxs if idx in self.inmem_buffer]

