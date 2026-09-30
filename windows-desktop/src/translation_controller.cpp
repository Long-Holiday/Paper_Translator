#include "translation_controller.h"
#include "app_paths.h"
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QTimer>
#include <stdexcept>
#ifdef Q_OS_WIN
#include <qt_windows.h>
#endif

TranslationController::TranslationController(PaperRepository &repository,QObject *parent)
    : QObject(parent),m_repository(repository) {
    m_process.setProcessChannelMode(QProcess::SeparateChannels);
#ifdef Q_OS_WIN
    m_process.setCreateProcessArgumentsModifier([](QProcess::CreateProcessArguments *args) {
        args->flags |= CREATE_NO_WINDOW;
    });
#endif
    connect(&m_process,&QProcess::readyReadStandardOutput,this,&TranslationController::readOutput);
    connect(&m_process,&QProcess::readyReadStandardError,this,[this] {
        auto bytes=m_process.readAllStandardError();
        if(m_log.isOpen() && m_log.size()<5*1024*1024) { m_log.write(bytes); m_log.flush(); }
    });
    connect(&m_process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,&TranslationController::finish);
    connect(&m_process,&QProcess::errorOccurred,this,[this](QProcess::ProcessError error) {
        if(error==QProcess::FailedToStart && m_active) {
            m_error="无法启动翻译引擎："+m_process.errorString();
            finish(-1,QProcess::CrashExit);
        }
    });
    connect(&m_process,&QProcess::started,this,[this] {
        auto p=m_repository.get(m_active);
        QJsonObject request{{"source",p.originalPath},{"output_dir",m_repository.paperDirectory(p.id)},
                            {"config",m_queue.head().config}, {"parent_pid",QCoreApplication::applicationPid()}};
        m_queue.dequeue();
        m_process.write(QJsonDocument(request).toJson(QJsonDocument::Compact)+'\n');
        m_process.closeWriteChannel();
    });
}
TranslationController::~TranslationController() { shutdown(); }
void TranslationController::setEngineCommand(const QString &program,const QStringList &arguments) {
    if(busy()) throw std::runtime_error("翻译运行中不能修改引擎命令");
    m_program=program; m_arguments=arguments;
}
bool TranslationController::busy() const { return m_active || !m_queue.isEmpty(); }
bool TranslationController::contains(qint64 id) const {
    if(id==m_active) return true;
    for(const auto &job:m_queue) if(job.id==id) return true;
    return false;
}
void TranslationController::enqueue(qint64 id) {
    if(contains(id)) return;
    const auto p=m_repository.get(id);
    if(!QFileInfo::exists(p.originalPath)) throw std::runtime_error("原文 PDF 不存在");
    const auto cfg=AppPaths::translationConfig();
    const auto service=cfg.value("service").toString();
    if((service=="deepseek" || service=="openai" || service=="zhipu" || service=="silicon") && cfg.value("api_key").toString().trimmed().isEmpty())
        throw std::runtime_error("请先在设置中填写翻译服务的 API Key");
    m_repository.setStatus(id,"queued",0); m_queue.enqueue({id,cfg});
    emit paperChanged(id);
    if(!m_active) QTimer::singleShot(0,this,&TranslationController::startNext);
}
void TranslationController::startNext() {
    if(m_stopping || m_active || m_queue.isEmpty()) return;
    m_active=m_queue.head().id; m_progress=0; m_buffer.clear(); m_result.clear(); m_error.clear(); m_cancelled=false;
    m_repository.setStatus(m_active,"translating",0);
    emit aboutToTranslate(m_active); emit paperChanged(m_active);
    QDir().mkpath(m_repository.root()+"/logs");
    m_log.setFileName(m_repository.root()+QString("/logs/translation-%1.log").arg(m_active));
    if(!m_log.open(QIODevice::WriteOnly|QIODevice::Truncate))
        emit message("无法写入翻译日志："+m_log.errorString());
    auto env=QProcessEnvironment::systemEnvironment();
    env.insert("PYTHONIOENCODING","utf-8"); env.insert("PYTHONUNBUFFERED","1");
    env.insert("PAPER_TRANSLATOR_HOME",m_repository.root()); m_process.setProcessEnvironment(env);
    QString program=m_program; auto args=m_arguments;
    if(program.isEmpty()) {
        program=AppPaths::engineExecutable();
        if(program.isEmpty()) { program=AppPaths::pythonExecutable(); args={"-u",AppPaths::engineScript()}; }
    }
    if(program.isEmpty()) {
        m_queue.dequeue(); m_error="找不到 Python。请安装翻译依赖并在设置中指定 Python，或使用含引擎的安装包。";
        finish(-1,QProcess::CrashExit); return;
    }
    m_process.setWorkingDirectory(m_repository.root());
    m_process.start(program,args);
}
void TranslationController::readOutput() {
    m_buffer+=m_process.readAllStandardOutput();
    if(m_buffer.size()>1024*1024) { m_error="翻译引擎输出超出协议限制"; m_process.kill(); return; }
    while(m_buffer.contains('\n')) {
        auto line=m_buffer.left(m_buffer.indexOf('\n')); m_buffer.remove(0,line.size()+1);
        if(line.trimmed().isEmpty()) continue;
        QJsonParseError error;
        const auto doc=QJsonDocument::fromJson(line,&error);
        if(error.error!=QJsonParseError::NoError || !doc.isObject()) {
            m_error="翻译引擎输出了无效消息，请查看翻译日志"; m_process.kill(); return;
        }
        if(!m_active) continue;
        const auto obj=doc.object();
        const auto type=obj.value("type").toString();
        if(type=="progress") {
            m_progress=qMax(m_progress,qBound(0,obj.value("progress").toInt(),99));
            m_repository.setStatus(m_active,"translating",m_progress);
            emit message(obj.value("message").toString()); emit paperChanged(m_active);
        } else if(type=="result") m_result=obj.value("path").toString();
        else if(type=="error") m_error=obj.value("message").toString().left(4096);
    }
}
void TranslationController::finish(int exitCode,QProcess::ExitStatus status) {
    if(!m_active) return;
    readOutput();
    const auto id=m_active;
    // A start failure leaves the active request at the head of the queue.
    if(!m_queue.isEmpty() && m_queue.head().id==id) m_queue.dequeue();
    try {
        if(m_cancelled) m_repository.setStatus(id,"failed",0,"翻译已取消，可重新翻译");
        else if(exitCode==0 && status==QProcess::NormalExit && !m_result.isEmpty() && m_error.isEmpty() && m_buffer.trimmed().isEmpty()) {
            m_repository.complete(id,m_result); emit message("翻译完成");
        } else m_repository.setStatus(id,"failed",0,m_error.isEmpty() ? "翻译引擎异常退出，请查看数据目录中的 logs" : m_error);
    } catch(const std::exception &exc) {
        m_repository.setStatus(id,"failed",0,QString::fromUtf8(exc.what()));
    }
    m_log.close(); m_active=0; emit paperChanged(id);
    if(!m_stopping) QTimer::singleShot(0,this,&TranslationController::startNext);
}
void TranslationController::cancel(qint64 id) {
    if(id==m_active) { m_cancelled=true; m_process.kill(); return; }
    for(int i=0;i<m_queue.size();++i) if(m_queue[i].id==id) {
        m_queue.removeAt(i); m_repository.setStatus(id,"failed",0,"翻译已取消，可重新翻译"); emit paperChanged(id); return;
    }
}
void TranslationController::shutdown() {
    if(m_stopping) return;
    m_stopping=true;
    if(m_active) { m_cancelled=true; m_process.kill(); m_process.waitForFinished(5000); if(m_active) finish(-1,QProcess::CrashExit); }
    while(!m_queue.isEmpty()) { const auto id=m_queue.dequeue().id; m_repository.setStatus(id,"failed",0,"关闭软件，翻译已取消"); }
}
