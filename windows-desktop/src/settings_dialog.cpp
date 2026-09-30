#include "settings_dialog.h"
#include "app_paths.h"
#include <QComboBox>
#include <QDialogButtonBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPushButton>
#include <QSettings>
#include <QSpinBox>
#include <QVBoxLayout>

SettingsDialog::SettingsDialog(QWidget *parent) : QDialog(parent) {
    setWindowTitle("翻译设置"); setMinimumWidth(560);
    auto layout=new QVBoxLayout(this); auto form=new QFormLayout; layout->addLayout(form);
    const auto cfg=AppPaths::translationConfig();
    m_service=new QComboBox; m_service->addItems({"deepseek","openai","zhipu","silicon","ollama","google","bing"});
    m_service->setCurrentText(cfg.value("service").toString()); form->addRow("翻译服务",m_service);
    auto field=[&](const QString &name,const QString &key) {
        auto edit=new QLineEdit(cfg.value(key).toString()); form->addRow(name,edit); return edit;
    };
    m_model=field("模型","model"); m_key=field("API Key","api_key"); m_key->setEchoMode(QLineEdit::Password);
    m_url=field("服务地址","base_url"); m_source=field("源语言","source_language"); m_target=field("目标语言","target_language");
    m_threads=new QSpinBox; m_threads->setRange(1,16); m_threads->setValue(cfg.value("thread").toInt(4)); form->addRow("翻译线程数",m_threads);
    auto pythonRow=new QHBoxLayout; m_python=new QLineEdit;
    QSettings settings(AppPaths::settingsFile(),QSettings::IniFormat);
    m_python->setText(settings.value("engine/python").toString()); m_python->setPlaceholderText("自动检测；分发包优先使用内置引擎");
    auto browse=new QPushButton("选择…"); pythonRow->addWidget(m_python,1); pythonRow->addWidget(browse); form->addRow("Python 路径",pythonRow);
    connect(browse,&QPushButton::clicked,this,[this] {
        auto path=QFileDialog::getOpenFileName(this,"选择 Python 解释器"); if(!path.isEmpty()) m_python->setText(path);
    });
    auto hint=new QLabel("设置对新加入队列的任务生效。首次翻译需要下载模型与字体。\nAPI Key 保存在本机用户配置中。");
    hint->setStyleSheet("color:#64748b;"); layout->addWidget(hint);
    auto buttons=new QDialogButtonBox(QDialogButtonBox::Save|QDialogButtonBox::Cancel); layout->addWidget(buttons);
    connect(buttons,&QDialogButtonBox::accepted,this,&SettingsDialog::save); connect(buttons,&QDialogButtonBox::rejected,this,&QDialog::reject);
    connect(m_service,&QComboBox::currentTextChanged,this,[this](const QString &service) {
        const QMap<QString,QPair<QString,QString>> defaults{
            {"deepseek",{"deepseek-chat","https://api.deepseek.com"}},
            {"openai",{"gpt-4o-mini","https://api.openai.com/v1"}},
            {"zhipu",{"glm-4-flash","https://open.bigmodel.cn/api/paas/v4"}},
            {"silicon",{"Qwen/Qwen2.5-7B-Instruct","https://api.siliconflow.cn/v1"}},
            {"ollama",{"qwen2.5","http://127.0.0.1:11434"}}, {"google",{"",""}}, {"bing",{"",""}}};
        const auto value=defaults.value(service); m_model->setText(value.first); m_url->setText(value.second);
    });
}
void SettingsDialog::save() {
    if(m_source->text().trimmed().isEmpty() || m_target->text().trimmed().isEmpty()) {
        QMessageBox::warning(this,"设置无效","源语言和目标语言不能为空"); return;
    }
    QSettings s(AppPaths::settingsFile(),QSettings::IniFormat);
    s.setValue("translation/service",m_service->currentText()); s.setValue("translation/model",m_model->text().trimmed());
    s.setValue("translation/api_key",m_key->text().trimmed()); s.setValue("translation/base_url",m_url->text().trimmed());
    s.setValue("translation/source_language",m_source->text().trimmed()); s.setValue("translation/target_language",m_target->text().trimmed());
    s.setValue("translation/thread",m_threads->value()); s.setValue("engine/python",m_python->text().trimmed()); s.sync();
    if(s.status()!=QSettings::NoError) { QMessageBox::warning(this,"保存失败","无法写入配置文件"); return; }
    accept();
}
