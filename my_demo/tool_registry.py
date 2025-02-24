import copy
import inspect
from pprint import pformat
import traceback
from types import GenericAlias
from typing import get_origin, Annotated,get_args
import hashlib
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from config import *

_TOOL_HOOKS = {}
_TOOL_DESCRIPTIONS = {}

embeddings = HuggingFaceEmbeddings(model_name='model',
                                       model_kwargs={'device': 'cpu'})

db = FAISS.load_local(DB_FAISS_PATH, embeddings)

def register_tool(func: callable):
    tool_name = func.__name__
    tool_description = inspect.getdoc(func).strip()
    python_params = inspect.signature(func).parameters
    tool_params = []

    for name, param in python_params.items():
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            raise TypeError(f"Parameter `{name}` missing type annotation")
        if get_origin(annotation) != Annotated:
            raise TypeError(f"Annotation type for `{name}` must be typing.Annotated")
        
        # 获取原始类型和元数据
        typ = get_origin(annotation)
        metadata = get_args(annotation)[1]  # 获取第二个元素，即元数据

        # 检查元数据是否为两个元素的元组
        if not isinstance(metadata, tuple) or len(metadata) != 2:
            raise TypeError(f"Metadata for `{name}` must be a tuple with two elements (description, required)")

        description, required = metadata
        typ: str = str(typ) if isinstance(typ, GenericAlias) else typ.__name__
        if not isinstance(description, str):
            raise TypeError(f"Description for `{name}` must be a string")
        if not isinstance(required, bool):
            raise TypeError(f"Required for `{name}` must be a bool")

        tool_params.append({
            "name": name,
            "description": description,
            "type": typ,
            "required": required
        })

    tool_def = {
        "name": tool_name,
        "description": tool_description,
        "params": tool_params
    }

    print("[registered tool] " + pformat(tool_def))
    _TOOL_HOOKS[tool_name] = func
    _TOOL_DESCRIPTIONS[tool_name] = tool_def

    return func

def dispatch_tool(tool_name: str, tool_params: dict) -> str:
    if tool_name not in _TOOL_HOOKS:
        return f"Tool `{tool_name}` not found. Please use a provided tool."
    tool_call = _TOOL_HOOKS[tool_name]
    try:
        ret = tool_call(**tool_params)  
    except:
        ret = traceback.format_exc()
    return str(ret)

def get_tools() -> dict:
    return copy.deepcopy(_TOOL_DESCRIPTIONS)

# Tool Definitions

@register_tool
def get_weather(
    city_name: Annotated[str, ("The name of the city to be queried", True)],
) -> str:
    """
    Get the current weather for `city_name`
    """
    if not isinstance(city_name, str):
        raise TypeError("City name must be a string")

    key_selection = {
        "current_condition": ["temp_C", "FeelsLikeC", "humidity", "weatherDesc",  "observation_time"],
    }
    import requests
    try:
        resp = requests.get(f"https://wttr.in/{city_name}?format=j1")
        resp.raise_for_status()
        resp = resp.json()
        ret = {k: {_v: resp[k][0][_v] for _v in v} for k, v in key_selection.items()}
    except:
        import traceback
        ret = "Error encountered while fetching weather data!\n" + traceback.format_exc() 

    return str(ret)


@register_tool
def generate_md5(input_string: Annotated[str, ("The input string to hash", True)]) -> str:
    """
    Generate MD5 hash of the provided string.
    """
    if not isinstance(input_string, str):
        raise TypeError("Input string must be a string")

    return hashlib.md5(input_string.encode()).hexdigest()


@register_tool
def search_knowledge_base(
    query_text: Annotated[str, ("The text to query in the net security knowledge base", True)]
) -> str:
    """
    Search the knowledge base for documents similar to the provided query text.
    """
    if not isinstance(query_text, str):
        raise TypeError("Query text must be a string")

    try:
        # 使用 `embed_query` 生成查询文本的嵌入向量
        query_embedding = embeddings.embed_query(query_text)

        # 使用 `similarity_search_by_vector` 在FAISS索引中搜索最相似的文档
        similar_documents = db.similarity_search_by_vector(query_embedding, k=4)  # k指定返回的相似文档数量

        # 组合相似文档的内容
        return '\n\n'.join([f'第 {index + 1} 段: {doc.page_content}' for index, doc in enumerate(similar_documents)])
    except Exception as e:
        return f"Error encountered while searching the knowledge base: {str(e)}"

@register_tool
def query_ip(
    ip_address: Annotated[str, ("The IP address to query", True)]
) -> str:
    """
    Query information about a given IP address.
    """
    if not isinstance(ip_address, str):
        raise TypeError("IP address must be a string")

    import requests
    try:
        response = requests.get(f"worker-tight-flower-09d8.cliuxinxin.workers.dev/?ip={ip_address}")
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error encountered while querying IP address: {str(e)}"


if __name__ == "__main__":
    print(dispatch_tool("get_weather", {"city_name": "beijing"}))
    print(get_tools())
