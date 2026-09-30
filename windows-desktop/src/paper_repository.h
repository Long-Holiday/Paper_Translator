#pragma once
#include <QList>
#include <QSqlDatabase>
#include <QString>

struct Paper {
    qint64 id = 0;
    QString title, filename, originalPath, translatedPath, status, error, createdAt;
    int pages = 0, progress = 0, lastPage = 1;
};

class PaperRepository {
public:
    explicit PaperRepository(const QString &root);
    ~PaperRepository();
    PaperRepository(const PaperRepository &) = delete;
    PaperRepository &operator=(const PaperRepository &) = delete;
    QList<Paper> list(const QString &search = {}) const;
    Paper get(qint64 id) const;
    Paper importPdf(const QString &source);
    int importLegacy(const QString &dataDirectory);
    void remove(qint64 id);
    void savePosition(qint64 id, int page);
    void setStatus(qint64 id, const QString &status, int progress, const QString &error = {});
    void complete(qint64 id, const QString &path);
    QString paperDirectory(qint64 id) const;
    QString root() const { return m_root; }
private:
    QString resolvePath(const QString &stored, qint64 id) const;
    QString m_root, m_connection;
    QSqlDatabase m_db;
};
