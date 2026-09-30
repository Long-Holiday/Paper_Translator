#include "main_window.h"
#include "app_paths.h"
#include "reader_widget.h"
#include "settings_dialog.h"
#include <QCloseEvent>
#include <QDesktopServices>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QMessageBox>
#include <QPushButton>
#include <QSignalBlocker>
#include <QStackedWidget>
#include <QStatusBar>
#include <QTableWidget>
#include <QUrl>
#include <QVBoxLayout>
#include <stdexcept>

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent),
    m_repository(AppPaths::userRoot()),m_translations(m_repository,this) {
    setWindowTitle("Paper Translator · 论文翻译阅读器"); resize(1440,960); setMinimumSize(960,640);
    setStyleSheet("QMainWindow,QDialog{background:#f8fafc;} QPushButton{padding:7px 14px;}"
                  "QLineEdit{padding:7px;} QTableWidget{background:white;gridline-color:#e2e8f0;}"
                  "QHeaderView::section{background:#eff6ff;padding:8px;border:0;} QLabel{color:#0f172a;}");
    auto fileMenu=menuBar()->addMenu("文件");
    auto legacy=fileMenu->addAction("导入旧项目论文库…");
    fileMenu->addAction("打开数据目录",this,[this]{ QDesktopServices::openUrl(QUrl::fromLocalFile(m_repository.root())); });
    fileMenu->addSeparator(); fileMenu->addAction("退出",this,&QWidget::close);
    menuBar()->addAction("设置",this,[this]{ SettingsDialog(this).exec(); });
    auto help=menuBar()->addMenu("帮助");
    help->addAction("关于",this,[this]{ QMessageBox::about(this,"关于 Paper Translator",
        "Paper Translator 2.0\nC++ / Qt 原生桌面客户端\nPDFMathTranslate Python 翻译引擎\n论文与设置保存在本机用户目录。"); });
    m_stack=new QStackedWidget; setCentralWidget(m_stack);
    auto library=new QWidget; auto layout=new QVBoxLayout(library); layout->setContentsMargins(24,18,24,18);
    auto heading=new QLabel("我的论文库"); heading->setStyleSheet("font-size:24px;font-weight:600;"); layout->addWidget(heading);
    auto subtitle=new QLabel("导入英文论文，保留数学公式与排版，双栏对照阅读。"); subtitle->setStyleSheet("color:#64748b;"); layout->addWidget(subtitle);
    auto bar=new QHBoxLayout; m_search=new QLineEdit; m_search->setPlaceholderText("搜索论文标题或文件名");
    auto import=new QPushButton("导入 PDF…"); auto settings=new QPushButton("翻译设置");
    bar->addWidget(m_search,1); bar->addWidget(import); bar->addWidget(settings); layout->addLayout(bar);
    m_table=new QTableWidget(0,6); m_table->setObjectName("paperTable");
    m_table->setHorizontalHeaderLabels({"论文标题","页数","翻译状态","进度","阅读位置","导入时间"});
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows); m_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers); m_table->setAlternatingRowColors(true);
    m_table->verticalHeader()->hide(); m_table->horizontalHeader()->setSectionResizeMode(0,QHeaderView::Stretch);
    for(int i=1;i<6;++i) m_table->horizontalHeader()->setSectionResizeMode(i,QHeaderView::ResizeToContents);
    layout->addWidget(m_table,1);
    auto actions=new QHBoxLayout;
    m_open=new QPushButton("打开阅读器"); m_translate=new QPushButton("开始 / 重新翻译");
    m_cancel=new QPushButton("取消翻译"); m_export=new QPushButton("导出译文…"); m_delete=new QPushButton("删除论文");
    for(auto button:{m_open,m_translate,m_cancel,m_export,m_delete}) actions->addWidget(button);
    actions->addStretch(); layout->addLayout(actions);
    m_stack->addWidget(library); m_reader=new ReaderWidget; m_stack->addWidget(m_reader);
    connect(m_search,&QLineEdit::textChanged,this,[this]{ reload(); });
    connect(settings,&QPushButton::clicked,this,[this]{ SettingsDialog(this).exec(); });
    connect(import,&QPushButton::clicked,this,[this] {
        const auto files=QFileDialog::getOpenFileNames(this,"导入论文 PDF",{},"PDF 文件 (*.pdf)");
        QStringList errors;
        for(const auto &file:files) {
            try { m_repository.importPdf(file); } catch(const std::exception &exc) { errors<<QFileInfo(file).fileName()+"："+QString::fromUtf8(exc.what()); }
        }
        reload(); if(!errors.isEmpty()) QMessageBox::warning(this,"部分文件导入失败",errors.join('\n'));
    });
    connect(legacy,&QAction::triggered,this,[this] {
        const auto dir=QFileDialog::getExistingDirectory(this,"选择旧项目 data 目录（包含 app.db 与 papers）"); if(dir.isEmpty()) return;
        try { const auto count=m_repository.importLegacy(dir); reload(); statusBar()->showMessage(QString("已导入 %1 篇论文，请在设置中配置翻译服务").arg(count),8000); }
        catch(const std::exception &exc) { showError(exc); }
    });
    connect(m_open,&QPushButton::clicked,this,[this]{ openPaper(selectedId()); });
    connect(m_table,&QTableWidget::cellDoubleClicked,this,[this]{ openPaper(selectedId()); });
    connect(m_translate,&QPushButton::clicked,this,[this]{ translate(selectedId()); });
    connect(m_cancel,&QPushButton::clicked,this,[this]{ try { m_translations.cancel(selectedId()); } catch(const std::exception &exc) { showError(exc); } });
    connect(m_export,&QPushButton::clicked,this,[this]{ exportPdf(selectedId()); });
    connect(m_delete,&QPushButton::clicked,this,[this] {
        const auto id=selectedId(); if(!id) return;
        if(QMessageBox::question(this,"删除论文","删除论文记录、原文和译文 PDF？")!=QMessageBox::Yes) return;
        try { if(m_reader->paperId()==id) m_reader->clear(); m_repository.remove(id); reload(); }
        catch(const std::exception &exc) { showError(exc); }
    });
    connect(m_table,&QTableWidget::itemSelectionChanged,this,[this] {
        const auto id=selectedId(); const bool active=m_translations.contains(id);
        m_open->setEnabled(id); m_translate->setEnabled(id && !active); m_cancel->setEnabled(id && active); m_delete->setEnabled(id && !active);
        m_export->setEnabled(id && !active && QFileInfo::exists(m_repository.get(id).translatedPath));
    });
    connect(m_reader,&ReaderWidget::backRequested,this,[this]{ m_stack->setCurrentIndex(0); reload(); });
    connect(m_reader,&ReaderWidget::translationRequested,this,&MainWindow::translate);
    connect(m_reader,&ReaderWidget::exportRequested,this,&MainWindow::exportPdf);
    connect(m_reader,&ReaderWidget::positionChanged,this,[this](qint64 id,int page) {
        try { m_repository.savePosition(id,page); statusBar()->showMessage(QString("阅读位置已保存 · 第 %1 页").arg(page)); }
        catch(const std::exception &exc) { showError(exc); }
    });
    connect(&m_translations,&TranslationController::aboutToTranslate,m_reader,&ReaderWidget::releaseTranslation);
    connect(&m_translations,&TranslationController::paperChanged,this,[this](qint64 id) {
        reload(); m_reader->refreshTranslation(m_repository.get(id));
    });
    connect(&m_translations,&TranslationController::message,statusBar(),[this](const QString &text){ statusBar()->showMessage(text); });
    reload();
}
void MainWindow::showError(const std::exception &error) { QMessageBox::warning(this,"操作失败",QString::fromUtf8(error.what())); }
qint64 MainWindow::selectedId() const {
    auto item=m_table->item(m_table->currentRow(),0); return item ? item->data(Qt::UserRole).toLongLong() : 0;
}
void MainWindow::reload() {
    const auto selected=selectedId();
    QSignalBlocker blocker(m_table);
    auto papers=m_repository.list(m_search->text()); m_table->setRowCount(papers.size()); int selectedRow=-1;
    const QMap<QString,QString> statuses{{"pending","未翻译"},{"queued","等待翻译"},{"translating","翻译中"},{"completed","已完成"},{"failed","失败 / 已取消"}};
    for(int row=0;row<papers.size();++row) {
        const auto &p=papers[row];
        const QStringList values{p.title,QString::number(p.pages),statuses.value(p.status,p.status),QString::number(p.progress)+"%",
            QString("%1 / %2").arg(p.lastPage).arg(p.pages),p.createdAt.left(10)};
        for(int col=0;col<values.size();++col) {
            auto item=new QTableWidgetItem(values[col]); item->setToolTip(col==2 && !p.error.isEmpty() ? p.error : values[col]);
            if(col==0) item->setData(Qt::UserRole,p.id);
            m_table->setItem(row,col,item);
        }
        if(p.id==selected) selectedRow=row;
    }
    if(selectedRow>=0) m_table->selectRow(selectedRow);
    else { m_table->clearSelection(); m_table->setCurrentCell(-1,-1); }
    const auto id=selectedId(); const bool active=m_translations.contains(id);
    m_open->setEnabled(id); m_translate->setEnabled(id && !active); m_cancel->setEnabled(id && active); m_delete->setEnabled(id && !active);
    m_export->setEnabled(id && !active && QFileInfo::exists(m_repository.get(id).translatedPath));
}
void MainWindow::openPaper(qint64 id) {
    if(!id) return;
    try { m_reader->openPaper(m_repository.get(id)); m_stack->setCurrentIndex(1); }
    catch(const std::exception &exc) { showError(exc); }
}
void MainWindow::translate(qint64 id) {
    if(!id) return;
    try { m_translations.enqueue(id); } catch(const std::exception &exc) { showError(exc); }
}
void MainWindow::exportPdf(qint64 id) {
    if(!id) return;
    try {
        if(m_translations.contains(id)) throw std::runtime_error("请等待翻译完成后再导出");
        auto p=m_repository.get(id); if(!QFileInfo::exists(p.translatedPath)) throw std::runtime_error("尚无译文 PDF");
        auto path=QFileDialog::getSaveFileName(this,"导出中文译文",QFileInfo(p.filename).completeBaseName()+"-中文.pdf","PDF (*.pdf)");
        if(path.isEmpty()) return;
        if(!path.endsWith(".pdf",Qt::CaseInsensitive)) path+=".pdf";
        AppPaths::copyFile(p.translatedPath,path); statusBar()->showMessage("译文已导出",5000);
    } catch(const std::exception &exc) { showError(exc); }
}
void MainWindow::closeEvent(QCloseEvent *event) {
    if(m_translations.busy() && QMessageBox::question(this,"退出","仍有翻译任务。退出将取消任务，确定退出？")!=QMessageBox::Yes) { event->ignore(); return; }
    m_translations.shutdown(); m_reader->clear(); event->accept();
}
