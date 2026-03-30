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

def load_data():
    """加载穴位数据"""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

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
    for keyword in keywords:
        if keyword in query_lower or query_lower in keyword:
            return True
    # 支持部分匹配
    for keyword in keywords:
        if len(keyword) >= 2 and len(query_lower) >= 2:
            if keyword[:2] in query_lower or query_lower[:2] in keyword:
                return True
    return False

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

@app.post("/api/search", response_model=SearchResponse)
async def search_acupoints(request: SearchRequest):
    """
    搜索穴位推荐
    - query: 症状描述
    - conditions: 辨证条件列表（如：受寒、急躁、乏力等）
    """
    data = load_data()
    results = []

    # 遍历所有病症
    for symptom in data["symptoms"]:
        # 检查是否匹配症状
        if fuzzy_match(request.query, symptom["keywords"]) or request.query in symptom["name"]:
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

    if not results:
        return SearchResponse(
            results=[],
            message="未找到匹配的病症，请尝试其他关键词，如：头痛、失眠、胃痛等"
        )

    return SearchResponse(
        results=results,
        message=f"找到 {len(results)} 个相关推荐"
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
