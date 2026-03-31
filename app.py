"""
智能针灸辨证选穴助手 (AcuPredictor) - 后端 API
基于中医针灸理论推荐核心穴位及其配伍逻辑
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
import re

# 初始化 FastAPI 应用
app = FastAPI(
    title="智能针灸辨证选穴助手",
    description="基于中医针灸理论的智能选穴系统",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 加载穴位数据
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "acupoints.json")
MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "symptom_mappings.json")

# 全局变量缓存数据
_acupoints_data = None
_symptom_mappings = None

def load_data():
    """加载穴位数据"""
    global _acupoints_data
    if _acupoints_data is None:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _acupoints_data = json.load(f)
    return _acupoints_data

def load_mappings():
    """加载症状映射数据"""
    global _symptom_mappings
    if _symptom_mappings is None:
        with open(MAPPINGS_PATH, "r", encoding="utf-8") as f:
            _symptom_mappings = json.load(f)
    return _symptom_mappings

# 请求模型
class SearchRequest(BaseModel):
    query: str
    conditions: Optional[List[str]] = []

# 响应模型
class AcupointResult(BaseModel):
    symptom: str
    pattern: str
    meridian: str
    main_points: List[str]
    auxiliary_points: List[str]
    logic: str
    needle_tips: str
    point_details: Dict

class SearchResponse(BaseModel):
    results: List[AcupointResult]
    message: str

def fuzzy_match(query: str, keywords: List[str]) -> bool:
    """模糊匹配症状关键词"""
    query_lower = query.lower()
    # 首先尝试精确匹配
    for keyword in keywords:
        if keyword in query_lower or query_lower in keyword:
            return True
    # 支持部分匹配（至少2个字符）
    for keyword in keywords:
        if len(keyword) >= 2 and len(query_lower) >= 2:
            if keyword[:2] in query_lower or query_lower[:2] in keyword:
                return True
    # 支持单字匹配（1个字的情况）
    if len(query_lower) == 1:
        for keyword in keywords:
            if query_lower in keyword:
                return True
    return False

def map_user_symptom(query: str, mappings: Dict) -> str:
    """
    将用户输入的症状描述映射到标准疾病名称
    返回映射后的症状，如果没有匹配则返回原查询
    """
    query_lower = query.strip().lower()

    # 遍历所有映射
    for mapping in mappings.get("mappings", []):
        target_disease = mapping.get("target_disease", "")
        # 检查是否匹配标准症状名称
        if query_lower == mapping.get("symptom", "").lower():
            return target_disease

        # 检查是否匹配描述列表中的任何一个
        for desc in mapping.get("descriptions", []):
            desc_lower = desc.lower()
            # 完全包含匹配
            if desc_lower in query_lower or query_lower in desc_lower:
                return target_disease

            # 部分匹配（至少2个字符）
            if len(query_lower) >= 2 and len(desc_lower) >= 2:
                if query_lower[:2] in desc_lower or desc_lower[:2] in query_lower:
                    return target_disease

    # 如果没有找到映射，返回原查询
    return query

def find_related_symptoms(query: str, mappings: Dict, limit: int = 5) -> List[str]:
    """
    查找相关症状，用于搜索建议
    """
    query_lower = query.lower()
    related = []

    # 首先尝试通过映射找到相关疾病
    for mapping in mappings.get("mappings", []):
        target_disease = mapping.get("target_disease", "")

        # 如果查询与任何描述部分匹配
        for desc in mapping.get("descriptions", []):
            if len(query_lower) >= 2 and len(desc_lower) >= 2:
                if query_lower[:2] in desc_lower or desc_lower[:2] in query_lower:
                    if target_disease not in related:
                        related.append(target_disease)
                        if len(related) >= limit:
                            return related
                    break
        if len(related) >= limit:
            break

    return related

def match_pattern(conditions: List[str], pattern_conditions: List[str]) -> int:
    """匹配辨证类型，返回匹配得分"""
    if not conditions:
        return 0
    score = 0
    for cond in conditions:
        for pattern_cond in pattern_conditions:
            if cond in pattern_cond or pattern_cond in cond:
                score += 1
    return score

def get_point_details(point_name: str, acupoints_info: Dict) -> Dict:
    """获取穴位详细信息"""
    if point_name in acupoints_info:
        return {
            "name": point_name,
            "location": acupoints_info[point_name]["location"],
            "meridian": acupoints_info[point_name]["meridian"]
        }
    return {"name": point_name, "location": "暂无定位信息", "meridian": "未知"}

@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

@app.get("/api/symptoms")
async def get_all_symptoms():
    """获取所有支持的病症列表"""
    data = load_data()
    symptoms = []
    for symptom in data["symptoms"]:
        symptoms.append({
            "id": symptom["id"],
            "name": symptom["name"],
            "keywords": symptom["keywords"],
            "patterns": list(symptom["patterns"].keys())
        })
    return {"symptoms": symptoms}

@app.get("/api/suggest")
async def get_suggestions(query: str = "", limit: int = 10):
    """
    获取搜索建议
    - query: 搜索关键词
    - limit: 返回的建议数量
    """
    if not query or len(query) < 1:
        return {"suggestions": []}

    data = load_data()
    mappings = load_mappings()
    suggestions = []
    seen = set()

    # 首先检查症状映射
    for mapping in mappings.get("mappings", []):
        target_disease = mapping.get("target_disease", "")
        if target_disease in seen:
            continue

        # 检查标准症状名称
        if query.lower() in mapping.get("symptom", "").lower():
            suggestions.append({
                "name": target_disease,
                "type": "mapped",
                "description": "已匹配到标准疾病名称"
            })
            seen.add(target_disease)

        # 检查描述列表
        for desc in mapping.get("descriptions", []):
            if query.lower() in desc.lower():
                suggestions.append({
                    "name": target_disease,
                    "type": "description",
                    "description": f"匹配症状描述：{desc}"
                })
                seen.add(target_disease)
                break

        if len(suggestions) >= limit:
            return {"suggestions": suggestions}

    # 如果映射结果不足，检查原始数据的关键词
    for symptom in data["symptoms"]:
        if symptom["name"] in seen:
            continue

        if fuzzy_match(query, symptom["keywords"]):
            suggestions.append({
                "name": symptom["name"],
                "type": "direct",
                "description": "直接匹配疾病关键词"
            })
            seen.add(symptom["name"])

        if len(suggestions) >= limit:
            return {"suggestions": suggestions}

    return {"suggestions": suggestions}

@app.post("/api/search", response_model=SearchResponse)
async def search_acupoints(request: SearchRequest):
    """
    搜索穴位推荐
    - query: 症状描述
    - conditions: 辨证条件列表（如：受寒、急躁、乏力等）
    """
    data = load_data()
    mappings = load_mappings()
    results = []

    # 步骤1: 将用户输入映射到标准症状
    mapped_query = map_user_symptom(request.query, mappings)
    original_query = request.query

    # 步骤2: 遍历所有病症进行匹配
    for symptom in data["symptoms"]:
        # 使用映射后的查询进行匹配，同时也检查原始查询
        if (fuzzy_match(mapped_query, symptom["keywords"]) or mapped_query in symptom["name"] or
            fuzzy_match(original_query, symptom["keywords"]) or original_query in symptom["name"]):

            # 获取所有辨证类型
            patterns = symptom["patterns"]

            # 计算每个辨证类型的匹配得分
            pattern_scores = {}
            for pattern_name, pattern_data in patterns.items():
                score = match_pattern(request.conditions, pattern_data["condition"])
                pattern_scores[pattern_name] = score

            # 如果有条件匹配，选择得分最高的；否则返回所有
            if request.conditions and any(s > 0 for s in pattern_scores.values()):
                best_patterns = [p for p, s in pattern_scores.items() if s == max(pattern_scores.values())]
            else:
                # 没有条件时返回所有辨证类型
                best_patterns = list(patterns.keys())

            # 构建结果
            for pattern_name in best_patterns:
                pattern_data = patterns[pattern_name]

                # 获取穴位详情
                main_point_details = {
                    p: get_point_details(p, data["acupoints_info"])
                    for p in pattern_data["main_points"]
                }
                aux_point_details = {
                    p: get_point_details(p, data["acupoints_info"])
                    for p in pattern_data["auxiliary_points"]
                }

                result = AcupointResult(
                    symptom=symptom["name"],
                    pattern=pattern_name,
                    meridian=pattern_data["meridian"],
                    main_points=pattern_data["main_points"],
                    auxiliary_points=pattern_data["auxiliary_points"],
                    logic=pattern_data["logic"],
                    needle_tips=pattern_data["needle_tips"],
                    point_details={**main_point_details, **aux_point_details}
                )
                results.append(result)

    # 步骤3: 构建响应
    if results:
        # 如果进行了映射，添加提示信息
        message = f"找到 {len(results)} 个相关推荐"
        if mapped_query != original_query:
            # 找到的是映射结果
            if f"{mapped_query}" in [r["symptom"] for r in results]:
                message = f"已为您找到「{mapped_query}」相关推荐，输入「{original_query}」已智能匹配到该疾病"
        return SearchResponse(
            results=results,
            message=message
        )
    else:
        # 未找到匹配时，提供相关症状建议
        related_symptoms = find_related_symptoms(original_query, mappings, limit=8)
        suggestion = "请尝试其他关键词，如：头痛、失眠、胃痛等"
        if related_symptoms:
            suggestion = f"未找到「{original_query}」，您是否在找以下症状：{', '.join(related_symptoms[:5])}"
            if len(related_symptoms) > 5:
                suggestion += f" 等{len(related_symptoms)}种症状"

        return SearchResponse(
            results=[],
            message=suggestion
        )

@app.get("/api/acupoint/{name}")
async def get_acupoint(name: str):
    """获取单个穴位详情"""
    data = load_data()
    if name in data["acupoints_info"]:
        return {
            "name": name,
            **data["acupoints_info"][name]
        }
    raise HTTPException(status_code=404, detail=f"未找到穴位: {name}")

# 挂载静态文件
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
