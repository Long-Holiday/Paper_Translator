#pragma once
#include <QJsonObject>
#include <QString>

namespace AppPaths {
QString userRoot();
QString engineScript();
QString engineExecutable();
QString settingsFile();
QString pythonExecutable();
QJsonObject translationConfig();
void copyFile(const QString &source, const QString &destination);
}
