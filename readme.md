# Molecular Universe: 分子结构-气味可视化平台

## 项目简介

本项目为分子结构与气味的交互可视化平台，基于 Three.js、D3.js 等可视化库，支持分子结构空间与气味标签空间三维降维可视化、标签/特征共现分析、数据概览、分子对比、信息检索等多种功能，你可以在分子的宇宙中尽情探索，感受科学的未知和奇妙。

## 快速开始（先看这里）

### 1) 在线访问

- 地址：[https://czx0v0.github.io/HTML/molecular_universe.html](https://czx0v0.github.io/HTML/molecular_universe.html)
- 说明：GitHub 单文件大小有限制，在线版通常只放较小数据集。

### 2) 本地运行

1. 克隆项目并进入根目录（`molecular_universe.html` 同级目录）。
2. 启动静态服务（任选其一）：
  - VSCode Live Server
  - `python -m http.server 8000`
3. 浏览器访问本地地址（如 `http://localhost:8000/molecular_universe.html`）。

### 3) 数据生成

**约定：与 `molecular_universe.html` 同级（项目根目录）**，例如：

- `gs_lf_4983.json`（单文件）
- `gs_lf_4983.manifest.json` + `gs_lf_4983.molecules-lite.jsonl` + `gs_lf_4983.molecules/` + `gs_lf_4983.neighbors/`（分片）

生成到根目录（推荐，与前端下拉一致）：

```bash
python "./preprocess/data_preprocess.py" --size 4983 --output-dir "."
```

若输出到 `./data`：脚本会把 manifest 内路径写成带 `data/` 前缀；或保持无前缀时，**前端会先请求根目录，失败则自动再请求 `data/` 下同一路径**（单文件、manifest、lite、分片 chunk 均适用）。

示例（生成多档数据）：

```bash
python "./preprocess/data_preprocess.py" --size 512 --output-dir "."
python "./preprocess/data_preprocess.py" --size 1024 --output-dir "."
python "./preprocess/data_preprocess.py" --size 2048 --output-dir "."
```

### 4) 数据和前端数据集下拉框同步

- 当前是“**半自动**”：
  - 如果你生成的是已有命名（如 `gs_lf_1024.json`），前端下拉框会直接可用。
  - 如果是新尺寸（如 `gs_lf_3000.json`），需要在前端下拉框里新增一个选项。
- 分片模式（manifest）默认优先读取 `gs_lf_4983.manifest.json`，不存在时回退到 `gs_lf_4983.json`。

## 主要功能

1. 3D分子空间可视化：支持结构空间与标签空间的降维投影（PCA/t-SNE/UMAP），分子点按标签/特征/分子量编码，支持旋转、缩放、筛选与高亮。
2. 气味标签与特征筛选：支持多标签/特征筛选、共现分子高亮。
3. 分子对比：对比当前筛选分子，展示分子结构、SMILES、分子量、标签与特征。
4. 数据概览：签分子数分布条形图，以及TopN标签下的标签分子数分布条形图、分子标签数分布条形图、标签共现热力图、标签-特征热力图、标签共现和弦图、分子量小提琴图等统计图表，支持交互筛选、SVG导出与放大。
5. 信息检索：支持SMILES或标签名检索分子。
6. 主题切换：支持浅色/深色主题。

## 界面操作说明

### 顶部菜单栏

- 主页：展示两种位置编码方式下的3D分子散点图。每个画布中，鼠标左键拖动旋转，滚轮缩放，点击右下角可以放大。鼠标悬浮在粒子上可查看分子简介。点击粒子可查看分子详情。
- 数据概览：展示138种气味标签对应的标签分子数分布条形图，以及TopN标签下的标签分子数分布条形图、分子标签数分布条形图、标签共现热力图、标签-特征热力图、标签共现和弦图、分子量小提琴图。每个图表支持悬浮提示、放大显示与下载SVG。除分子标签数分布图外，均支持点击筛选。
- 分子对比：可对比当前加入已对比分子的结构、标签和特征，点击可跳转至对应分子详情。
- 信息查询：支持SMILES全名或标签全名检索分子，点击可跳转至对应分子详情。
- 帮助指引：点击问号查看操作说明，

### 左侧操作面板

- 数据集选择：可切换不同大小的数据集。
- 主题切换：可切换浅色/深色主题。
- TopN聚焦模式：可设置高频标签的数量，切换高亮模式。
- 清空筛选：可清空当前筛选。
- 降维方式：可选择PCA、t-SNE或UMAP降维方式。
- SMILES/散点切换：可切换显示分子SMILES或仅显示分子点。
- 共现排行榜：展示气味标签共现/气味+特征标签共现数目排行榜Top12，点击可筛选对应的两个标签。
- 气味标签筛选：可选择感兴趣的气味标签进行筛选。
- 特征筛选：可选择感兴趣的分子特征进行筛选。
- 分子量范围滑块：控制显示分子的最大分子量。
- 分子数目上限滑块：控制显示的最大分子数目。

### 右侧信息面板

- 分子详情：显示分子SMILES、IUPAC名称、2D结构图、气味标签云和特征标签云。其中气味标签云和特征标签云可点击筛选。点击复制可复制分子SMILES。点击加入对比可将分子加入对比。

## 主界面视觉编码

- 点颜色：表示为气味标签。可在左侧切换TopN高频标签模式或全部色彩模式。
- 当选中标签（特征）的数目为1时，全部红色高亮。
- 当选中标签（特征）的数目大于1时，有其中一种标签（特征）的显示为彩色，包含全部选中标签的标识为红色高亮。
- 点大小：表示分子量大小。
- 点坐标：共有基于分子指纹的（结构空间）以及基于分子气味标签的（气味空间）两种方式表示点位置，可选择PCA、t-SNE或UMAP降维方式。
- 图例:左侧为点的颜色表示的气味特征，红色边框为当前筛选。中间为分子量大小示意。右侧指示红色为共现。

## 数据概览界面视觉编码

- 标签分子数分布条形图：每个柱表示TopN/Top138标签下每个气味标签的分子数分布，颜色表示气味标签，和主界面颜色对应，选中的标签颜色变为粉红色。
- 分子标签数分布条形：每个柱表示TopN标签下每个气味标签的分子数分布。
- 标签共现热力图：横轴和纵轴均表示气味标签，标签每个格表示TopN标签下气味标签共现次数，两个标签共现次数多颜色深。
- 标签-特征热力图：横轴表示特征标签，纵轴表示气味标签，每个格表示TopN标签下特征出现次数，两个标签共现次数多颜色深。
- 标签共现和弦图：每个环形分段表示TopN标签下每个气味标签，颜色表示气味标签。每条弦表示Top20标签间的共现关系，弦宽代表共现次数。
- 分子量小提琴图：横轴表示气味标签，纵轴表示分子量大小。每个小提琴表示Top20标签下平均分子量分布，颜色表示气味标签。

## 数据集

1. 原始数据集：[OpenPOM](https://github.com/BioMachineLearning/openpom/blob/main/openpom/data/curated_datasets/curated_GS_LF_merged_4983.csv)
2. 主数据文件：在根目录文件夹中。
3. json数据格式说明：
  1. labels/features：与 label_names/feature_names 顺序一一对应。
  2. fp_coords/lb_coords：结构/标签空间的降维坐标。
  3. 详细格式如下：

```json
{
  "metadata": {
    "label_names": ["fruity", "woody", ...],         // csv文件第3-140列的列名，代表气味描述符
    "feature_names": [
      "sulfur",
      "carboxylic_acid",
      "alkyl_four_carbon_chain",
      "ester",
      "phenyl",
      "eight_atoms_or_fewer",
      "ether",
      "aldehyde",
      "hitrile",
      "thirteen_atoms_or_more",
      "aromatic_nitrogen",
      "amine"
    ] //12种特征标签，参考POM论文
  },
  "molecules": [
    {
      "smiles": "CCO",
      "labels": [0, 1, 0, ...],  // 138维数组，与label_names对应
      "features": [0, 1, 0, ...],  // 12维数组，与feature_names对应
      "label_nums":3,
      "descriptors": "alcoholic;woody;",
      "properties": {
        "molecular_weight": 46.07,                  // 用RDKit计算
        "logP": 0.35,                               // 用RDKit计算
        "is_aromatic": false,              // 是否含芳香环用RDKit计算，判断分子是否含芳香环（True/False）
              "elements": ["C", "H", "O"],       // 组成元素列表（去重），RDKit计算，子中存在的元素符号列表（去重，按原子序数排序）
              "iupac_name": "ethanol",           // 学名，pubchempy计算，IUPAC名称（通过PubChem API查询，失败时设为"N/A"）
      },
      "fp_coords": {                               // 分子指纹降维坐标
        "pca": [1.2, -0.3, 0.8],
        "tsne": [0.5, 1.1, -0.2],
        "umap": [-0.7, 0.4, 1.0]
      },
      "lb_coords": {                               // 气味标签降维坐标
        "pca": [1.2, -0.3, 0.8],
        "tsne": [0.5, 1.1, -0.2],
        "umap": [-0.7, 0.4, 1.0]
      }
    },
    // ...（其他分子）
  ]
}
```

1. 数据转换（CSV -> JSON/分片）
  1. 见 `./preprocess/data_preprocess.py`，将原始CSV转换为前端可视化数据。
  2. 推荐用法（输出到项目根目录，便于前端直接读取）：

```bash
python "./preprocess/data_preprocess.py" --size 2048 --output-dir "."
```

1. 常用参数说明：
  - `--size`：处理分子数量
  - `--output-dir`：输出目录（建议 `"."`）
  - `--chunk-size`：分片大小（manifest模式）
  - `--topk`：每个分子的近邻数量
  - `--output-mode`：`dual/single/chunk`
  - `--skip-neighbors`：跳过近邻计算（更快）
  - `--skip-shards`：只输出单文件 JSON（兼容模式）
  - `--skip-full-json`：不输出单文件 JSON
2. 输出产物（示例）：
  - `gs_lf_2048.json`（单文件）
  - `gs_lf_2048.manifest.json`（分片入口）
  - `gs_lf_2048.molecules-lite.jsonl`
  - `gs_lf_2048.molecules/chunk_0000.json`
  - `gs_lf_2048.neighbors/chunk_0000.json`

### 依赖环境

- Three.js (3D可视化)
- D3.js (统计图表)
- SmilesDrawer (分子2D结构渲染)

### 致谢&参考

- Three.js
- D3.js
- SmilesDrawer
- Embedding Projector
- [OpenPOM - Open Principal Odor Map, Aryan Amit Barsainyan and Ritesh Kumar and Pinaki Saha and Michael Schmuker](https://github.com/BioMachineLearning/openpom)
- A Principal Odor Map Unifies Diverse Tasks in Human Olfactory Perception.
Science381,999-1006(2023).DOI: 10.1126/science.ade4401
- 其他开源数据与可视化工具的贡献者

### 更新日志

#### 2025.06.15(v0.0.1)

- 基本功能实现和线上发布。

#### 2025.11.12(v0.1.1)

- 修改源，防止网络问题无法初始化数据。

#### 2026.01.24(v0.2.0)

- 更新第二版data_preprocess处理，修改t-SNE。
- 分子指纹统一为1024维。

#### 2026.01.27(v0.2.1)

- 更新第三版data_preprocess处理，暂时去除similarity_matrix。
- 修复HTML文件的问题。

#### 2026.03.12(v0.2.3)

- 修复github pages和本地的json数据存放位置不一致导致的数据读取失败问题。

#### 2026.03.21(v0.2.4)

- **数据与预处理**：`data_preprocess` 支持 `--output-mode`（dual/single/chunk）、`--skip-full-json`；manifest 内 lite/分片路径在输出到子目录时自动带相对前缀，避免静态站路径错位。
- **相似度存储**：延续 TopK 邻居分片（结构 Tanimoto + 标签 Jaccard），替代全量相似矩阵，控制体积与加载成本。
- **前端加载**：根目录请求失败时自动再试 `data/` 同一路径；默认数据集为 **4983 分片 manifest**，默认渲染模式为 **chunk_mode**。
- **相似推荐**：单文件模式下可后台挂载同名 manifest 的邻居分片，使 `hybrid_lod` / `full_image` 也能按需展示推荐（仍依赖邻居产物）。

### 后续计划

1. 支持深度学习embeddings和自定义文件可视化。
2. 支持更多类型的科学数据如谱图文件可视化。
3. 接入大语言模型API。

## 性能实验

1. 模式定义：
  - `full_image`：全量分子图压力模式（强调渲染开销）
  - `hybrid_lod`：LOD模式（平衡可读性与性能）
  - `chunk_mode`：分片加载模式（强调加载与内存）
2. 采样方式：
  - 每个模式点击“采样20秒”，按相同交互脚本执行（缩放、筛选、详情）。
3. 导出：
  - 点击“导出性能日志JSON”，得到同口径日志。
4. 建议指标：
  - `render_fps_avg/p95`
  - `frame_time_ms_p50/p95/p99`
  - `long_task_count/total_ms`
  - `memory_peak_mb`
  - `webgl_context_lost_count`
5. 汇总报告（ `perf_report.py`）：

```bash
python "./preprocess/perf_report.py" --inputs "./perf_run.json" --output "./data/perf_report.md"
```

`--output` 可写任意路径；写到 `data/` 时若目录不存在会自动创建。可把多次导出合并进同一个 JSON 或传多个 `--inputs` 文件。

## 数据标准接口（本地 preprocess）

推荐命令（统一接口）：

```bash
python "./preprocess/data_preprocess.py" --size 2048 --output-dir "." --output-mode dual
```

`--output-mode` 说明：

- `dual`：单文件 + 分片（推荐，实验默认）
- `single`：仅单文件
- `chunk`：仅分片

