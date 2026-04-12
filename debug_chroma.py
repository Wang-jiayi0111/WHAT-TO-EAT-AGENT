import sys
sys.path.insert(0, 'F:/WHAT-TO-EAT-AGENT')
 
from src.libs.base.chroma_store import ChromaStore
from src.libs.adapters.embed.embed_factory import EmbedFactory
from src.libs.base.settings import Settings
 
settings = Settings()
embedding_fn = EmbedFactory.get_embed(settings)
store = ChromaStore(
    db_path='F:/WHAT-TO-EAT-AGENT/data/db',
    embedding_function=embedding_fn,
    collection_name='recipes'
)

results = store.query('红烧肉', 2)
for r in results:
    print(repr(r.get('content','')[:200]))  # 用 repr 看真实的换行符
    print("---")