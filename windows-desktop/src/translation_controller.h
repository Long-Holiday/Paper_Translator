#pragma once
#include <QFile>
#include <QJsonObject>
#include <QObject>
#include <QProcess>
#include <QQueue>
#include "paper_repository.h"

class TranslationController : public QObject {
    Q_OBJECT
public:
    explicit TranslationController(PaperRepository &repository,QObject *parent=nullptr);
    ~TranslationController() override;
    void enqueue(qint64 id);
    void cancel(qint64 id);
    void shutdown();
    bool busy() const;
    bool contains(qint64 id) const;
    void setEngineCommand(const QString &program,const QStringList &arguments);
signals:
    void paperChanged(qint64 id);
    void aboutToTranslate(qint64 id);
    void message(const QString &text);
private:
    struct Job { qint64 id; QJsonObject config; };
    void startNext();
    void readOutput();
    void finish(int exitCode,QProcess::ExitStatus status);
    PaperRepository &m_repository;
    QQueue<Job> m_queue;
    QProcess m_process;
    QFile m_log;
    qint64 m_active=0;
    QByteArray m_buffer;
    QString m_result,m_error,m_program;
    QStringList m_arguments;
    bool m_stopping=false,m_cancelled=false;
    int m_progress=0;
};
