#include "paper_repository.h"
#include "app_paths.h"
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QPdfDocument>
#include <QSqlError>
#include <QSqlQuery>
#include <QUuid>
#include <stdexcept>

namespace {
void check(bool ok, const QSqlQuery &q) {
    if (!ok) throw std::runtime_error(q.lastError().text().toStdString());
}
const QString columns = "id,title,original_filename,original_pdf_path,translated_pdf_path,"
                        "translation_status,translation_progress,translation_error,page_count,last_read_page,created_at";
Paper fromQuery(const QSqlQuery &q) {
    Paper p;
    p.id=q.value(0).toLongLong(); p.title=q.value(1).toString(); p.filename=q.value(2).toString();
    p.originalPath=q.value(3).toString(); p.translatedPath=q.value(4).toString();
    p.status=q.value(5).toString(); p.progress=q.value(6).toInt(); p.error=q.value(7).toString();
    p.pages=q.value(8).toInt(); p.lastPage=qMax(1,q.value(9).toInt()); p.createdAt=q.value(10).toString();
    return p;
}
}

PaperRepository::PaperRepository(const QString &root)
    : m_root(QDir(root).absolutePath()), m_connection(QUuid::createUuid().toString()) {
    if (!QDir().mkpath(m_root + "/data/papers")) throw std::runtime_error("无法创建论文目录");
    m_db = QSqlDatabase::addDatabase("QSQLITE", m_connection);
    m_db.setDatabaseName(m_root + "/data/app.db");
    if (!m_db.open()) throw std::runtime_error(m_db.lastError().text().toStdString());
    QSqlQuery q(m_db);
    check(q.exec("PRAGMA busy_timeout=5000"),q);
    check(q.exec("CREATE TABLE IF NOT EXISTS papers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,original_filename TEXT NOT NULL,"
        "original_pdf_path TEXT NOT NULL,translated_pdf_path TEXT,page_count INTEGER,"
        "translation_status TEXT NOT NULL DEFAULT 'pending',translation_progress INTEGER NOT NULL DEFAULT 0,"
        "translation_error TEXT,last_read_page INTEGER NOT NULL DEFAULT 1,created_at TEXT,updated_at TEXT)"),q);
    check(q.exec("UPDATE papers SET translation_status='failed',translation_progress=0,"
                 "translation_error='上次翻译已中断，请重新翻译' WHERE translation_status IN ('queued','translating')"),q);
}
PaperRepository::~PaperRepository() {
    m_db.close(); m_db=QSqlDatabase(); QSqlDatabase::removeDatabase(m_connection);
}
QString PaperRepository::paperDirectory(qint64 id) const {
    return m_root + "/data/papers/" + QString::number(id);
}
QString PaperRepository::resolvePath(const QString &stored, qint64 id) const {
    if (stored.isEmpty()) return {};
    auto normalized=stored; normalized.replace('\\','/');
    const auto local=paperDirectory(id)+"/"+QFileInfo(normalized).fileName();
    if (QFileInfo::exists(local)) return local;
    return QDir::isAbsolutePath(normalized) ? normalized : QDir(m_root+"/data").filePath(normalized);
}
QList<Paper> PaperRepository::list(const QString &search) const {
    QSqlQuery q(m_db);
    q.prepare("SELECT "+columns+" FROM papers WHERE title LIKE ? OR original_filename LIKE ? ORDER BY id DESC");
    q.addBindValue("%"+search.trimmed()+"%"); q.addBindValue("%"+search.trimmed()+"%");
    check(q.exec(),q);
    QList<Paper> result;
    while(q.next()) {
        auto p=fromQuery(q);
        p.originalPath=resolvePath(p.originalPath,p.id); p.translatedPath=resolvePath(p.translatedPath,p.id);
        result.append(p);
    }
    return result;
}
Paper PaperRepository::get(qint64 id) const {
    QSqlQuery q(m_db); q.prepare("SELECT "+columns+" FROM papers WHERE id=?"); q.addBindValue(id);
    check(q.exec(),q);
    if (!q.next()) throw std::runtime_error("论文不存在");
    auto p=fromQuery(q); p.originalPath=resolvePath(p.originalPath,p.id); p.translatedPath=resolvePath(p.translatedPath,p.id);
    return p;
}
Paper PaperRepository::importPdf(const QString &source) {
    QPdfDocument doc;
    if (doc.load(source)!=QPdfDocument::Error::None || doc.pageCount()<1)
        throw std::runtime_error("PDF 无法读取、已加密或没有页面");
    auto title=doc.metaData(QPdfDocument::MetaDataField::Title).toString().trimmed();
    if (title.isEmpty()) title=QFileInfo(source).completeBaseName();
    const int pages=doc.pageCount(); doc.close();
    if (!m_db.transaction()) throw std::runtime_error("无法开始数据库事务");
    qint64 id=0;
    bool createdDirectory=false;
    try {
        QSqlQuery q(m_db);
        q.prepare("INSERT INTO papers(title,original_filename,original_pdf_path,page_count,created_at,updated_at) VALUES(?,?,'',?,?,?)");
        q.addBindValue(title); q.addBindValue(QFileInfo(source).fileName()); q.addBindValue(pages);
        auto now=QDateTime::currentDateTimeUtc().toString(Qt::ISODate); q.addBindValue(now); q.addBindValue(now);
        check(q.exec(),q); id=q.lastInsertId().toLongLong();
        if (QDir(paperDirectory(id)).exists()) throw std::runtime_error("论文目录已存在，请先备份并检查用户数据");
        if (!QDir().mkpath(paperDirectory(id))) throw std::runtime_error("无法创建论文目录");
        createdDirectory=true;
        AppPaths::copyFile(source,paperDirectory(id)+"/original.pdf");
        q.prepare("UPDATE papers SET original_pdf_path=? WHERE id=?");
        q.addBindValue(QString("papers/%1/original.pdf").arg(id)); q.addBindValue(id); check(q.exec(),q);
        if (!m_db.commit()) throw std::runtime_error("无法保存论文记录");
    } catch (...) {
        m_db.rollback(); if (createdDirectory) QDir(paperDirectory(id)).removeRecursively(); throw;
    }
    return get(id);
}
void PaperRepository::savePosition(qint64 id,int page) {
    QSqlQuery q(m_db);
    q.prepare("UPDATE papers SET last_read_page=MAX(1,MIN(?,page_count)),updated_at=? WHERE id=?");
    q.addBindValue(page); q.addBindValue(QDateTime::currentDateTimeUtc().toString(Qt::ISODate)); q.addBindValue(id);
    check(q.exec(),q);
}
void PaperRepository::setStatus(qint64 id,const QString &status,int progress,const QString &error) {
    QSqlQuery q(m_db);
    q.prepare("UPDATE papers SET translation_status=?,translation_progress=?,translation_error=?,updated_at=? WHERE id=?");
    q.addBindValue(status); q.addBindValue(qBound(0,progress,100)); q.addBindValue(error);
    q.addBindValue(QDateTime::currentDateTimeUtc().toString(Qt::ISODate)); q.addBindValue(id); check(q.exec(),q);
}
void PaperRepository::complete(qint64 id,const QString &path) {
    QPdfDocument doc;
    if (QFileInfo(path).canonicalFilePath()!=QFileInfo(paperDirectory(id)+"/translated.pdf").canonicalFilePath()
        || !QFileInfo::exists(path) || doc.load(path)!=QPdfDocument::Error::None || doc.pageCount()!=get(id).pages)
        throw std::runtime_error("翻译输出无效或页数不匹配");
    doc.close();
    QSqlQuery q(m_db);
    q.prepare("UPDATE papers SET translated_pdf_path=?,translation_status='completed',translation_progress=100,translation_error=NULL WHERE id=?");
    q.addBindValue(QString("papers/%1/translated.pdf").arg(id)); q.addBindValue(id); check(q.exec(),q);
}
void PaperRepository::remove(qint64 id) {
    const auto p=get(id);
    if (p.status=="queued" || p.status=="translating") throw std::runtime_error("请先取消该论文的翻译任务");
    // Rename first so a failed database deletion can restore the files.
    const auto dir=paperDirectory(id), trash=dir+".deleted-"+QUuid::createUuid().toString(QUuid::WithoutBraces);
    const bool hadDir=QDir(dir).exists();
    if (hadDir && !QDir().rename(dir,trash)) throw std::runtime_error("无法删除 PDF，请关闭占用文件的阅读器");
    QSqlQuery q(m_db); q.prepare("DELETE FROM papers WHERE id=?"); q.addBindValue(id);
    if (!q.exec()) { if(hadDir) QDir().rename(trash,dir); check(false,q); }
    if(hadDir) QDir(trash).removeRecursively();
}
int PaperRepository::importLegacy(const QString &dataDirectory) {
    if(!list().isEmpty()) throw std::runtime_error("旧论文库仅可导入到空论文库，以免覆盖现有数据");
    const auto name=QUuid::createUuid().toString();
    auto old=QSqlDatabase::addDatabase("QSQLITE",name);
    old.setDatabaseName(QDir(dataDirectory).filePath("app.db")); old.setConnectOptions("QSQLITE_OPEN_READONLY");
    QList<qint64> copied;
    try {
        if(!old.open()) throw std::runtime_error("无法读取旧论文库 app.db");
        QSqlQuery read(old); check(read.exec("SELECT "+columns+" FROM papers"),read);
        if(!m_db.transaction()) throw std::runtime_error("无法开始导入事务");
        while(read.next()) {
            auto p=fromQuery(read);
            if(QDir(paperDirectory(p.id)).exists()) throw std::runtime_error("目标论文目录已存在，请先备份并检查用户数据");
            if(!QDir().mkpath(paperDirectory(p.id))) throw std::runtime_error("无法创建论文目录");
            copied.append(p.id);
            for (const auto &kind : {QString("original"),QString("translated")}) {
                const auto path=kind=="original" ? p.originalPath : p.translatedPath;
                if(path.isEmpty() && kind=="translated") continue;
                auto normalized=path; normalized.replace('\\','/');
                auto file=QDir(dataDirectory).filePath(QString("papers/%1/%2").arg(p.id).arg(QFileInfo(normalized).fileName()));
                if(!QFileInfo::exists(file)) throw std::runtime_error(QString("旧论文 %1 文件缺失").arg(p.id).toStdString());
                AppPaths::copyFile(file,paperDirectory(p.id)+"/"+kind+".pdf");
            }
            QSqlQuery write(m_db);
            write.prepare("INSERT INTO papers("+columns+") VALUES(?,?,?,?,?,?,?,?,?,?,?)");
            write.addBindValue(p.id); write.addBindValue(p.title); write.addBindValue(p.filename);
            write.addBindValue(QString("papers/%1/original.pdf").arg(p.id));
            write.addBindValue(p.translatedPath.isEmpty() ? QVariant() : QVariant(QString("papers/%1/translated.pdf").arg(p.id)));
            const bool stale=p.status=="queued" || p.status=="translating";
            write.addBindValue(stale ? "failed" : p.status); write.addBindValue(stale ? 0 : p.progress);
            write.addBindValue(stale ? "旧任务已中断，请重新翻译" : p.error);
            write.addBindValue(p.pages); write.addBindValue(p.lastPage); write.addBindValue(p.createdAt); check(write.exec(),write);
        }
        if(!m_db.commit()) throw std::runtime_error("保存导入数据失败");
    } catch (...) {
        m_db.rollback(); for(auto id:copied) QDir(paperDirectory(id)).removeRecursively();
        old.close(); old=QSqlDatabase(); QSqlDatabase::removeDatabase(name); throw;
    }
    old.close(); old=QSqlDatabase(); QSqlDatabase::removeDatabase(name); return copied.size();
}
