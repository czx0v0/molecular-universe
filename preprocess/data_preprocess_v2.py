import os

# 解决报错
os.environ["OMP_NUM_THREADS"] = "1"
# os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
import warnings

warnings.filterwarnings("ignore")
warnings.filterwarnings(
    "ignore", message=".*please use MorganGenerator.*", category=DeprecationWarning
)
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors, DataStructs
from rdkit.Chem.rdchem import Mol
from pubchempy import get_compounds
import numpy as np
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from umap.umap_ import UMAP
import json
from tqdm import tqdm
import argparse


def args_parser():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="数据处理脚本")
    parser.add_argument("--size", type=int, default=1024, help="处理的数据大小")
    parser.add_argument(
        "--input",
        type=str,
        default="./code/preprocess/curated_GS_LF_merged_4983.csv",
        help="输入文件路径",
    )
    args = parser.parse_args()
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

    tsne = TSNE(
        n_components=3,
        random_state=42,
        verbose=0,
        max_iter=1200,
        learning_rate="auto",
        perplexity=30,  # 困惑度（5-50）
        early_exaggeration=12.0,  # 早期放大
        n_iter_without_progress=300,  # 提前停止
        min_grad_norm=1e-7,  # 梯度阈值
        metric="euclidean",  # 距离度量
        init="random",
    )
    fp_tsne_coords = tsne.fit_transform(fingerprint_matrix)
    lb_tsne_coords = tsne.fit_transform(label_matrix)

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

    # 计算相似度矩阵
    n = len(molecules_data)

    # 结构相似度（Tanimoto）
    structural_sim = np.zeros((n, n))
    for i in range(n):
        structural_sim[i] = DataStructs.BulkTanimotoSimilarity(
            all_fingerprints[i], all_fingerprints
        )

    # 标签相似度（Jaccard）
    label_matrix = np.array(all_labels, dtype=bool)
    intersection = np.dot(label_matrix, label_matrix.T)
    sum_labels = label_matrix.sum(axis=1)
    union = sum_labels[:, None] + sum_labels[None, :] - intersection
    jaccard_sim = np.divide(
        intersection,
        union,
        out=np.zeros_like(intersection, dtype=float),  # 修正这里
        where=union != 0,
    )

    # 构建最终JSON
    output = {
        "metadata": {"label_names": label_names, "feature_names": feature_names},
        "molecules": molecules_data,
        "similarity_matrix": {
            "structural": structural_sim.tolist(),
            "label": jaccard_sim.tolist(),
        },
    }

    # 写入文件
    with open(f"gs_lf_{args.size}.json", "w") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    main(args_parser())
