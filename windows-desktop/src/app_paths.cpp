#include "app_paths.h"
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <stdexcept>

namespace AppPaths {
QString userRoot() {
    QString root = qEnvironmentVariable("PAPER_TRANSLATOR_HOME");
    if (root.isEmpty()) root = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    root = QDir(root).absolutePath();
    for (const auto &dir : {"data/papers", "config", "logs"}) {
        if (!QDir().mkpath(root + "/" + dir))
            throw std::runtime_error(QString("无法创建数据目录：%1").arg(root).toStdString());
    }
    return root;
}
QString engineScript() {
    const auto deployed = QCoreApplication::applicationDirPath() + "/engine/bridge.py";
    if (QFileInfo::exists(deployed)) return deployed;
    return QStringLiteral(PAPER_SOURCE_DIR) + "/engine/bridge.py";
}
QString engineExecutable() {
    const auto path = QCoreApplication::applicationDirPath() + "/engine/pdfmathtranslate-engine.exe";
    return QFileInfo::exists(path) ? path : QString();
}
QString settingsFile() { return userRoot() + "/config/settings.ini"; }
QString pythonExecutable() {
    QSettings settings(settingsFile(), QSettings::IniFormat);
    auto configured = settings.value("engine/python").toString().trimmed();
    if (!configured.isEmpty()) return configured;
#ifdef Q_OS_WIN
    const QString suffix = "/.venv/Scripts/python.exe";
#else
    const QString suffix = "/.venv/bin/python";
#endif
    const auto local = QStringLiteral(PAPER_SOURCE_DIR) + suffix;
    if (QFileInfo::exists(local)) return local;
    const auto adjacent = QFileInfo(QStringLiteral(PAPER_SOURCE_DIR)).dir().absolutePath() + suffix;
    if (QFileInfo::exists(adjacent)) return adjacent;
#ifdef Q_OS_WIN
    return QStandardPaths::findExecutable("python.exe");
#else
    return QStandardPaths::findExecutable("python3");
#endif
}
QJsonObject translationConfig() {
    QSettings s(settingsFile(), QSettings::IniFormat);
    QJsonObject cfg;
    const QJsonObject defaults{{"service", "deepseek"}, {"model", "deepseek-chat"},
        {"api_key", ""}, {"base_url", "https://api.deepseek.com"},
        {"source_language", "en"}, {"target_language", "zh"}, {"thread", 4}};
    for (auto it = defaults.begin(); it != defaults.end(); ++it)
        cfg.insert(it.key(), QJsonValue::fromVariant(s.value("translation/" + it.key(), it.value().toVariant())));
    return cfg;
}
void copyFile(const QString &source, const QString &destination) {
    if (QFileInfo(source).absoluteFilePath() == QFileInfo(destination).absoluteFilePath())
        throw std::runtime_error("源文件与目标文件相同");
    QFile input(source);
    QSaveFile output(destination);
    if (!input.open(QIODevice::ReadOnly) || !output.open(QIODevice::WriteOnly))
        throw std::runtime_error("无法打开 PDF 文件，请检查路径和权限");
    while (!input.atEnd()) {
        const auto bytes = input.read(1024 * 1024);
        if (bytes.isEmpty() && input.error() != QFile::NoError)
            throw std::runtime_error("读取 PDF 失败");
        if (output.write(bytes) != bytes.size()) throw std::runtime_error("写入 PDF 失败");
    }
    if (!output.commit()) throw std::runtime_error("保存 PDF 失败");
}
}
