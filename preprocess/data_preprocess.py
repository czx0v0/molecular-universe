import argparse
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pubchempy import get_compounds
from rdkit import Chem
from rdkit.Chem import DataStructs, Descriptors, rdMolDescriptors
from rdkit.Chem.rdchem import Mol
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from tqdm import tqdm
from umap.umap_ import UMAP

# 解决报错
os.environ["OMP_NUM_THREADS"] = "1"
# os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

warnings.filterwarnings("ignore")
warnings.filterwarnings(
    "ignore", message=".*please use MorganGenerator.*", category=DeprecationWarning
)


def args_parser():
    parser = argparse.ArgumentParser(description="数据处理脚本")
    parser.add_argument("--size", type=int, default=2048, help="处理的数据大小")
    parser.add_argument(
        "--input",
        type=str,
        default="./preprocess/curated_GS_LF_merged_4983.csv",
        help="输入文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data",
        help="输出目录（同时输出全量和分片产物）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="分片大小（用于 molecules/neighbors 分块）",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=20,
        help="为每个分子预计算 TopK 近邻",
    )
    parser.add_argument(
        "--skip-neighbors",
        action="store_true",
        help="跳过 TopK 近邻计算（更快）",
    )
    parser.add_argument(
        "--skip-shards",
        action="store_true",
        help="仅输出兼容旧版的单文件 JSON，不输出 manifest/chunk",
    )
    parser.add_argument(
        "--skip-full-json",
        action="store_true",
        help="不输出单文件 JSON，仅输出 manifest/chunk",
    )
    parser.add_argument(
        "--output-mode",
        type=str,
        default="dual",
        choices=["dual", "single", "chunk"],
        help="输出模式：dual(单文件+分片) / single(仅单文件) / chunk(仅分片)",
    )
    args = parser.parse_args()
    if args.output_mode == "single":
        args.skip_shards = True
        args.skip_full_json = False
    elif args.output_mode == "chunk":
        args.skip_shards = False
        args.skip_full_json = True
    return args


def compute_aromatic_rings(mol: Mol) -> bool:
    """检查分子是否含有芳香环"""
    ri = mol.GetRingInfo()
    for ring in ri.AtomRings():
        if all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring):
            return True
    return False


def get_iupac_name(smiles: str, timeout: int = 10) -> str:
    """通过PubChem查询IUPAC名称"""
    try:
        compounds = get_compounds(smiles, namespace="smiles", timeout=timeout)
        return compounds[0].iupac_name if compounds else "N/A"
    except Exception:
        return "N/A"


# 1. 定义12种结构特征的计算函数
def has_sulfur(mol):
    return int(any(atom.GetSymbol() == "S" for atom in mol.GetAtoms()))


def has_carboxylic_acid(mol):
    patt = Chem.MolFromSmarts("C(=O)O")
    return int(mol.HasSubstructMatch(patt))


def has_alkyl_four_carbon_chain(mol):
    patt = Chem.MolFromSmarts("CCCC")
    return int(mol.HasSubstructMatch(patt))


def has_ester(mol):
    patt = Chem.MolFromSmarts("C(=O)OC")
    return int(mol.HasSubstructMatch(patt))


def has_phenyl(mol):
    patt = Chem.MolFromSmarts("c1ccccc1")
    return int(mol.HasSubstructMatch(patt))


def has_eight_atoms_or_fewer(mol):
    return int(mol.GetNumAtoms() <= 8)


def has_ether(mol):
    patt = Chem.MolFromSmarts("COC")
    return int(mol.HasSubstructMatch(patt))


def has_aldehyde(mol):
    patt = Chem.MolFromSmarts("[CX3H1](=O)[#6]")
    return int(mol.HasSubstructMatch(patt))


def has_hitrile(mol):
    patt = Chem.MolFromSmarts("C#N")
    return int(mol.HasSubstructMatch(patt))


def has_thirteen_atoms_or_more(mol):
    return int(mol.GetNumAtoms() >= 13)


def has_aromatic_nitrogen(mol):
    patt = Chem.MolFromSmarts("n")
    return int(mol.HasSubstructMatch(patt))


def has_amine(mol):
    patt = Chem.MolFromSmarts("[NX3;H2,H1;!$(NC=O)]")
    return int(mol.HasSubstructMatch(patt))


def safe_tsne_fit(matrix: np.ndarray) -> np.ndarray:
    n = len(matrix)
    if n < 4:
        return np.zeros((n, 3), dtype=float)
    perplexity = max(2, min(30, n // 3))
    if perplexity >= n:
        perplexity = max(2, n - 1)
    tsne = TSNE(
        n_components=3,
        random_state=42,
        verbose=0,
        max_iter=1200,
        learning_rate="auto",
        perplexity=perplexity,
        early_exaggeration=12.0,
        n_iter_without_progress=300,
        min_grad_norm=1e-7,
        metric="euclidean",
        init="random",
    )
    return tsne.fit_transform(matrix)


def build_neighbors(
    fingerprints,
    all_labels: list[list[int]],
    topk: int,
) -> dict[int, dict[str, list[dict[str, float]]]]:
    label_bool = np.array(all_labels, dtype=bool)
    neighbors: dict[int, dict[str, list[dict[str, float]]]] = {}
    for i in tqdm(range(len(fingerprints)), desc="计算TopK近邻"):
        structural_scores = np.array(
            DataStructs.BulkTanimotoSimilarity(fingerprints[i], fingerprints),
            dtype=float,
        )
        structural_scores[i] = -1.0
        structural_ids = np.argsort(structural_scores)[::-1][:topk]

        intersection = np.logical_and(label_bool[i], label_bool).sum(axis=1).astype(float)
        union = np.logical_or(label_bool[i], label_bool).sum(axis=1).astype(float)
        label_scores = np.divide(
            intersection,
            union,
            out=np.zeros_like(intersection, dtype=float),
            where=union != 0,
        )
        label_scores[i] = -1.0
        label_ids = np.argsort(label_scores)[::-1][:topk]

        neighbors[i] = {
            "structural": [
                {"id": int(j), "score": float(structural_scores[j])} for j in structural_ids
            ],
            "label": [{"id": int(j), "score": float(label_scores[j])} for j in label_ids],
        }
    return neighbors


def chunk_ranges(total: int, chunk_size: int) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    chunk_idx = 0
    for start in range(0, total, chunk_size):
        end = min(total, start + chunk_size)
        ranges.append((chunk_idx, start, end))
        chunk_idx += 1
    return ranges


def main(args):
    feature_funcs = [
        has_sulfur,
        has_carboxylic_acid,
        has_alkyl_four_carbon_chain,
        has_ester,
        has_phenyl,
        has_eight_atoms_or_fewer,
        has_ether,
        has_aldehyde,
        has_hitrile,
        has_thirteen_atoms_or_more,
        has_aromatic_nitrogen,
        has_amine,
    ]
    feature_names = [
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
        "amine",
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 读取CSV文件
    df = pd.read_csv(f"{args.input}", sep=",", encoding="utf-8")
    label_names = df.columns[2:].tolist()  # 3-140列:descriptors

    molecules_data = []
    all_fingerprints = []
    all_labels = []

    # 只处理前k个分子
    for _, row in tqdm(df.head(args.size).iterrows(), total=args.size):
        smiles = row.iloc[0]
        descriptors = row.iloc[1]
        labels = row.iloc[2:].astype(int).tolist()

        # 解析SMILES
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            continue

        # 计算分子属性
        try:
            mol_weight = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
        except:
            continue

        is_aromatic = compute_aromatic_rings(mol)

        # 收集元素并排序
        elements = sorted(
            {atom.GetSymbol() for atom in mol.GetAtoms()},
            key=lambda x: Chem.GetPeriodicTable().GetAtomicNumber(x),
        )

        # 获取IUPAC名称
        iupac_name = get_iupac_name(smiles)

        # 生成ECFP4指纹
        fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
        all_fingerprints.append(fp)
        all_labels.append(labels)

        # 计算12种结构特征
        features = [func(mol) for func in feature_funcs]

        # 构建分子数据
        molecules_data.append(
            {
                "id": len(molecules_data),
                "smiles": smiles,
                "labels": labels,
                "features": features,
                "descriptors": descriptors,
                "properties": {
                    "molecular_weight": mol_weight,
                    "logP": logp,
                    "is_aromatic": is_aromatic,
                    "elements": elements,
                    "iupac_name": iupac_name,
                },
            }
        )

    # 指纹降维
    fingerprint_matrix = np.array([np.zeros(1024, dtype=int) for _ in all_fingerprints])
    for i, fp in enumerate(all_fingerprints):
        DataStructs.ConvertToNumpyArray(fp, fingerprint_matrix[i])
    # 标签降维
    label_matrix = np.array(all_labels, dtype=float)

    pca = PCA(
        n_components=3,
        random_state=42,
        svd_solver="auto",
        whiten=False,
        tol=0.0,
        iterated_power="auto",
    )
    fp_pca_coords = pca.fit_transform(fingerprint_matrix)
    lb_pca_coords = pca.fit_transform(label_matrix)

    fp_tsne_coords = safe_tsne_fit(fingerprint_matrix)
    lb_tsne_coords = safe_tsne_fit(label_matrix)

    umap = UMAP(
        n_components=3,
        random_state=42,
        n_epochs=300,
        spread=1.0,
        n_neighbors=15,
        min_dist=0.1,
        metric="euclidean",
        n_jobs=1,
        repulsion_strength=1.0,  # 排斥强度
        learning_rate=1.0,  # 学习率
        densmap=False,  # 是否保持密度
        verbose=False,
    )
    fp_umap_coords = umap.fit_transform(fingerprint_matrix)
    lb_umap_coords = umap.fit_transform(label_matrix)

    # 添加降维坐标到分子数据
    for i, molecule in enumerate(molecules_data):
        molecule["label_nums"] = int(np.sum(molecule["labels"]))
        molecule["fp_coords"] = {
            "pca": fp_pca_coords[i].tolist(),
            "tsne": fp_tsne_coords[i].tolist(),
            "umap": fp_umap_coords[i].tolist(),
        }
        molecule["lb_coords"] = {
            "pca": lb_pca_coords[i].tolist(),
            "tsne": lb_tsne_coords[i].tolist(),
            "umap": lb_umap_coords[i].tolist(),
        }
        # 如果有旧的 'embeddings' 字段，删除
        if "embeddings" in molecule:
            del molecule["embeddings"]

    dataset_size = len(molecules_data)
    dataset_name = f"gs_lf_{dataset_size}"
    full_json_name = f"{dataset_name}.json"

    # 构建兼容旧版的单文件JSON
    output = {
        "metadata": {
            "schema_version": "v2",
            "label_names": label_names,
            "feature_names": feature_names,
        },
        "molecules": molecules_data,
    }
    if not args.skip_full_json:
        full_json_path = output_dir / full_json_name
        with full_json_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"[OK] 写入单文件数据: {full_json_path}")

    if args.skip_shards:
        return

    # 浏览器 fetch 路径相对于「网站根目录」（与 molecular_universe.html 同级目录为根时）。
    # 若输出在子目录如 data/，manifest 内 lite/chunk 路径需带此前缀，否则会从根目录找错文件。
    try:
        _rel_out = Path(args.output_dir).resolve().relative_to(Path.cwd().resolve())
        _url_prefix = (
            ""
            if _rel_out == Path(".")
            else str(_rel_out).replace("\\", "/").strip("/") + "/"
        )
    except ValueError:
        _url_prefix = ""

    manifest_name = f"{dataset_name}.manifest.json"
    lite_path = output_dir / f"{dataset_name}.molecules-lite.jsonl"
    chunks_dir = output_dir / f"{dataset_name}.molecules"
    neighbors_dir = output_dir / f"{dataset_name}.neighbors"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    neighbors_dir.mkdir(parents=True, exist_ok=True)

    # 1) 写 lite（首屏必要字段）
    with lite_path.open("w", encoding="utf-8") as f:
        for mol in molecules_data:
            lite = {
                "id": mol["id"],
                "smiles": mol["smiles"],
                "labels": mol["labels"],
                "features": mol["features"],
                "label_nums": mol["label_nums"],
                "properties": {"molecular_weight": mol["properties"]["molecular_weight"]},
                "fp_coords": mol["fp_coords"],
                "lb_coords": mol["lb_coords"],
            }
            f.write(json.dumps(lite, ensure_ascii=False) + "\n")

    # 2) 写详情分片
    chunks_meta = []
    ranges = chunk_ranges(dataset_size, args.chunk_size)
    for chunk_idx, start, end in ranges:
        chunk_file = f"chunk_{chunk_idx:04d}.json"
        chunk_payload = {
            "chunk_idx": chunk_idx,
            "start": start,
            "end": end,
            "molecules": molecules_data[start:end],
        }
        with (chunks_dir / chunk_file).open("w", encoding="utf-8") as f:
            json.dump(chunk_payload, f, ensure_ascii=False)
        chunks_meta.append(
            {
                "chunk_idx": chunk_idx,
                "start": start,
                "end": end,
                "path": f"{_url_prefix}{dataset_name}.molecules/{chunk_file}",
            }
        )

    # 3) 写近邻分片
    neighbors_meta = []
    if not args.skip_neighbors:
        neighbors_by_id = build_neighbors(all_fingerprints, all_labels, args.topk)
        for chunk_idx, start, end in ranges:
            chunk_file = f"chunk_{chunk_idx:04d}.json"
            chunk_payload = {
                "chunk_idx": chunk_idx,
                "start": start,
                "end": end,
                "neighbors": {
                    str(i): neighbors_by_id[i] for i in range(start, end) if i in neighbors_by_id
                },
            }
            with (neighbors_dir / chunk_file).open("w", encoding="utf-8") as f:
                json.dump(chunk_payload, f, ensure_ascii=False)
            neighbors_meta.append(
                {
                    "chunk_idx": chunk_idx,
                    "start": start,
                    "end": end,
                    "path": f"{_url_prefix}{dataset_name}.neighbors/{chunk_file}",
                }
            )

    # 4) manifest（数据契约入口）
    manifest = {
        "schema_version": "v2",
        "dataset": {
            "name": dataset_name,
            "size": dataset_size,
            "legacy_path": (
                f"{_url_prefix}{full_json_name}" if not args.skip_full_json else ""
            ),
        },
        "metadata": {"label_names": label_names, "feature_names": feature_names},
        "layout": {
            "lite_path": f"{_url_prefix}{lite_path.name}",
            "chunk_size": args.chunk_size,
            "molecule_chunks": chunks_meta,
            "neighbor_chunks": neighbors_meta,
            "neighbor_topk": args.topk if not args.skip_neighbors else 0,
        },
    }
    manifest_path = output_dir / manifest_name
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[OK] 写入manifest: {manifest_path}")

    interface_path = output_dir / f"{dataset_name}.interface.json"
    interface = {
        "schema_version": "v2",
        "required_metadata_fields": ["label_names", "feature_names"],
        "required_molecule_fields": [
            "id",
            "smiles",
            "labels",
            "features",
            "properties.molecular_weight",
            "fp_coords.pca/tsne/umap",
            "lb_coords.pca/tsne/umap",
        ],
        "recommended_output_mode": "dual",
        "generated_with": {
            "size": dataset_size,
            "chunk_size": args.chunk_size,
            "topk": args.topk,
            "output_mode": args.output_mode,
        },
    }
    with interface_path.open("w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=2)
    print(f"[OK] 写入接口说明: {interface_path}")


if __name__ == "__main__":
    main(args_parser())
