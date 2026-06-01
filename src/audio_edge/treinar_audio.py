#!/usr/bin/env python3
"""
SENTINELA — Módulo de Áudio / Edge AI
======================================
Treina um classificador de sons de motosserra, trator e veículos
usando o dataset público ESC-50 e exporta para TensorFlow Lite,
pronto para ser embarcado num ESP32 via TFLite Micro.

Status: ✅ Funcional (treino + export TFLite)

Uso:
    python treinar_audio.py
    python treinar_audio.py --epochs 30 --model-path meu_modelo.tflite

Dependências:
    pip install tensorflow librosa soundfile numpy tqdm
"""

import os
import sys
import argparse
import zipfile
import urllib.request
import warnings
from pathlib import Path

import numpy as np
from tqdm import tqdm
from loguru import logger

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
ESC50_URL = "https://github.com/karolpiczak/ESC-50/archive/master.zip"
DATA_DIR = Path("data/esc50")
MODEL_DIR = Path("models")
SAMPLE_RATE = 22050
DURATION = 5        # segundos (padrão ESC-50)
N_MFCC = 40
N_MELS = 128

# Classes de interesse para o Sentinela
# ESC-50 tem 50 classes; usamos as que representam ameaças florestais + silêncio/floresta
CLASSES_INTERESSE = {
    "chainsaw": 1,          # motosserra ← PRINCIPAL
    "engine": 1,            # motor / trator
    "car_horn": 0,          # veículo (falso positivo potencial — classe neutra)
    "thunderstorm": 0,      # chuva / neutro
    "crickets": 0,          # floresta normal (silêncio natural)
}
LABEL_MAP = {"ameaca": 1, "normal": 0}


# ─────────────────────────────────────────────────────────────
# Download e preparação do ESC-50
# ─────────────────────────────────────────────────────────────
def baixar_esc50() -> Path:
    """Baixa o dataset ESC-50 se ainda não existir."""
    zip_path = DATA_DIR / "esc50.zip"
    extract_path = DATA_DIR / "ESC-50-master"

    if extract_path.exists():
        logger.info("ESC-50 já baixado em {}", extract_path)
        return extract_path

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando ESC-50 (~600 MB) …")

    def _progress(count, block_size, total_size):
        pct = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\r  {pct}%")
        sys.stdout.flush()

    urllib.request.urlretrieve(ESC50_URL, zip_path, reporthook=_progress)
    print()

    logger.info("Extraindo …")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(DATA_DIR)

    zip_path.unlink()
    logger.success("ESC-50 pronto em {}", extract_path)
    return extract_path


def carregar_metadados(esc_path: Path) -> list[dict]:
    """Lê o CSV de metadados e retorna lista de samples com label binário."""
    import csv

    csv_path = esc_path / "meta" / "esc50.csv"
    samples = []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            categoria = row["category"]
            if categoria in CLASSES_INTERESSE:
                audio_path = esc_path / "audio" / row["filename"]
                samples.append({
                    "path": str(audio_path),
                    "categoria": categoria,
                    "label": CLASSES_INTERESSE[categoria],
                })

    logger.info("{} amostras selecionadas das classes de interesse", len(samples))
    return samples


# ─────────────────────────────────────────────────────────────
# Extração de features MFCC
# ─────────────────────────────────────────────────────────────
def extrair_mfcc(audio_path: str) -> np.ndarray:
    """Extrai MFCCs de um arquivo de áudio e retorna tensor (N_MFCC, T, 1)."""
    import librosa

    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, duration=DURATION)
    # Pad ou trunca para exatamente DURATION segundos
    target_len = SAMPLE_RATE * DURATION
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)))
    else:
        y = y[:target_len]

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    mfcc = (mfcc - mfcc.mean()) / (mfcc.std() + 1e-8)  # normalização
    mfcc = mfcc[..., np.newaxis]  # (N_MFCC, T, 1)
    return mfcc


def preparar_dataset(samples: list[dict]):
    """Extrai features de todas as amostras e retorna X, y numpy arrays."""
    X, y = [], []
    logger.info("Extraindo features MFCC …")
    for s in tqdm(samples, desc="MFCC"):
        try:
            feat = extrair_mfcc(s["path"])
            X.append(feat)
            y.append(s["label"])
        except Exception as e:
            logger.warning("Erro em {}: {}", s["path"], e)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    logger.info("Dataset: X={}, y={}", X.shape, y.shape)
    return X, y


# ─────────────────────────────────────────────────────────────
# Modelo CNN para áudio
# ─────────────────────────────────────────────────────────────
def construir_modelo(input_shape: tuple):
    """
    CNN leve inspirada na arquitetura do EdgeImpulse / TinyML.
    Deve caber em ~256 KB de RAM (compatível com ESP32 PSRAM).
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models

    modelo = models.Sequential([
        layers.Input(shape=input_shape),

        # Bloco 1
        layers.Conv2D(16, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Bloco 2
        layers.Conv2D(32, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        # Bloco 3
        layers.Conv2D(64, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.GlobalAveragePooling2D(),
        layers.Dropout(0.5),

        # Classificador binário
        layers.Dense(64, activation="relu"),
        layers.Dropout(0.3),
        layers.Dense(1, activation="sigmoid"),
    ], name="sentinela_audio_cnn")

    modelo.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy", tf.keras.metrics.AUC(name="auc")],
    )
    return modelo


# ─────────────────────────────────────────────────────────────
# Treino
# ─────────────────────────────────────────────────────────────
def treinar(X: np.ndarray, y: np.ndarray, epochs: int = 20):
    """Treina o modelo e retorna o modelo treinado."""
    import tensorflow as tf
    from sklearn.model_selection import train_test_split

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    logger.info("Treino: {} amostras | Validação: {} amostras", len(X_train), len(X_val))

    modelo = construir_modelo(input_shape=X.shape[1:])
    modelo.summary()

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_auc", patience=5, restore_best_weights=True, mode="max"
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, verbose=1
        ),
    ]

    historico = modelo.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=16,
        callbacks=callbacks,
        verbose=1,
    )

    # Avaliação final
    val_loss, val_acc, val_auc = modelo.evaluate(X_val, y_val, verbose=0)
    logger.success("Val Loss={:.4f} | Acc={:.4f} | AUC={:.4f}", val_loss, val_acc, val_auc)

    return modelo, historico


# ─────────────────────────────────────────────────────────────
# Export TFLite
# ─────────────────────────────────────────────────────────────
def exportar_tflite(modelo, X_rep: np.ndarray, output_path: Path):
    """
    Converte o modelo para TFLite com quantização INT8 (full-integer),
    essencial para rodar no ESP32 com TFLite Micro.
    """
    import tensorflow as tf

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Salva modelo Keras
    keras_path = MODEL_DIR / "sentinela_audio.keras"
    modelo.save(keras_path)
    logger.info("Modelo Keras salvo em {}", keras_path)

    # 2. Converter para TFLite com quantização INT8
    converter = tf.lite.TFLiteConverter.from_keras_model(modelo)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    def representative_dataset():
        for i in range(min(100, len(X_rep))):
            yield [X_rep[i:i+1]]

    converter.representative_dataset = representative_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    tflite_model = converter.convert()

    with open(output_path, "wb") as f:
        f.write(tflite_model)

    size_kb = len(tflite_model) / 1024
    logger.success("Modelo TFLite INT8 salvo em {} ({:.1f} KB)", output_path, size_kb)

    # 3. Verificar inferência no modelo TFLite
    logger.info("Verificando inferência TFLite …")
    interpreter = tf.lite.Interpreter(model_path=str(output_path))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    amostra = X_rep[0:1]
    # Quantiza para INT8
    scale, zero_point = input_details[0]["quantization"]
    amostra_int8 = (amostra / scale + zero_point).astype(np.int8)

    interpreter.set_tensor(input_details[0]["index"], amostra_int8)
    interpreter.invoke()
    saida = interpreter.get_tensor(output_details[0]["index"])

    out_scale, out_zp = output_details[0]["quantization"]
    prob = (saida[0][0].astype(np.float32) - out_zp) * out_scale
    logger.success("Inferência OK — probabilidade de ameaça: {:.3f}", prob)

    return output_path


# ─────────────────────────────────────────────────────────────
# Modo demo (sem ESC-50 — usa dados sintéticos)
# ─────────────────────────────────────────────────────────────
def modo_demo(epochs: int, model_path: Path):
    """
    Executa um treino rápido com dados sintéticos para demonstração
    quando o ESC-50 não está disponível ou o usuário não tem internet.
    """
    logger.warning("Modo DEMO ativo — usando dados sintéticos (não use em produção!)")
    import tensorflow as tf

    # Simula MFCCs: (N, 40, 216, 1)
    N = 200
    T = 216  # frames para 5 s a sr=22050 com hop=512
    np.random.seed(42)

    # Classe 1 (motosserra): MFCC com padrão de alta frequência
    X_pos = np.random.randn(N // 2, N_MFCC, T, 1).astype(np.float32) + 1.5
    # Classe 0 (floresta): MFCC mais silencioso
    X_neg = np.random.randn(N // 2, N_MFCC, T, 1).astype(np.float32) - 0.5

    X = np.concatenate([X_pos, X_neg])
    y = np.concatenate([np.ones(N // 2), np.zeros(N // 2)]).astype(np.float32)

    idx = np.random.permutation(N)
    X, y = X[idx], y[idx]

    modelo, _ = treinar(X, y, epochs=min(epochs, 5))
    exportar_tflite(modelo, X[:50], model_path)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SENTINELA — Treina classificador de áudio para detecção de motosserras"
    )
    parser.add_argument("--epochs", type=int, default=20, help="Nº de épocas de treino")
    parser.add_argument("--model-path", type=Path, default=MODEL_DIR / "sentinela_audio.tflite",
                        help="Caminho de saída do modelo TFLite")
    parser.add_argument("--demo", action="store_true",
                        help="Usa dados sintéticos (sem baixar ESC-50)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  SENTINELA — Classificador de Áudio / Edge AI")
    logger.info("  Alvo: motosserra, trator, veículos pesados na Amazônia")
    logger.info("=" * 60)

    if args.demo:
        modo_demo(args.epochs, args.model_path)
        return

    try:
        esc_path = baixar_esc50()
        samples = carregar_metadados(esc_path)

        if len(samples) < 10:
            logger.warning("Poucas amostras, ativando modo demo")
            modo_demo(args.epochs, args.model_path)
            return

        X, y = preparar_dataset(samples)
        modelo, _ = treinar(X, y, epochs=args.epochs)
        exportar_tflite(modelo, X[:100], args.model_path)

    except Exception as e:
        logger.error("Erro durante execução: {}", e)
        logger.info("Ativando modo demo …")
        modo_demo(args.epochs, args.model_path)

    logger.success("Pronto! Modelo TFLite em: {}", args.model_path)
    logger.info("Próximo passo: incluir o .tflite no firmware ESP32 (sentinela_esp32.ino)")


if __name__ == "__main__":
    main()
