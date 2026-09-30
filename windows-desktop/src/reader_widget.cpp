#include "reader_widget.h"
#include <QCheckBox>
#include <QEvent>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QPdfDocument>
#include <QPdfPageNavigator>
#include <QPdfView>
#include <QPushButton>
#include <QScopedValueRollback>
#include <QScrollBar>
#include <QSignalBlocker>
#include <QSpinBox>
#include <QSplitter>
#include <QTimer>
#include <QVBoxLayout>
#include <QWheelEvent>
#include <stdexcept>

ReaderWidget::ReaderWidget(QWidget *parent) : QWidget(parent) {
    auto layout=new QVBoxLayout(this); layout->setContentsMargins(12,8,12,8);
    auto bar=new QHBoxLayout;
    auto back=new QPushButton("返回论文库"); bar->addWidget(back);
    m_title=new QLabel; m_title->setMinimumWidth(80); bar->addWidget(m_title,1);
    auto previous=new QPushButton("上一页"); auto next=new QPushButton("下一页");
    m_pageSpin=new QSpinBox; m_pageSpin->setRange(1,1); m_pageSpin->setObjectName("pageSpin");
    m_total=new QLabel("/ 0");
    bar->addWidget(previous); bar->addWidget(m_pageSpin); bar->addWidget(m_total); bar->addWidget(next);
    m_zoom=new QSpinBox; m_zoom->setRange(40,300); m_zoom->setSingleStep(10); m_zoom->setSuffix("%"); m_zoom->setValue(100);
    auto fit=new QPushButton("适合宽度"); bar->addWidget(m_zoom); bar->addWidget(fit);
    m_link=new QCheckBox("同步滚动"); m_link->setChecked(true); bar->addWidget(m_link);
    auto translate=new QPushButton("翻译"); auto exportPdf=new QPushButton("导出译文");
    bar->addWidget(translate); bar->addWidget(exportPdf); layout->addLayout(bar);
    m_original=new QPdfDocument(this); m_translated=new QPdfDocument(this);
    m_left=new QPdfView; m_right=new QPdfView;
    m_left->setObjectName("originalView"); m_right->setObjectName("translatedView");
    auto splitter=new QSplitter;
    auto pane=[&](QPdfView *view,const QString &caption,QLabel **label=nullptr) {
        auto widget=new QWidget; auto column=new QVBoxLayout(widget); column->setContentsMargins(0,0,0,0);
        auto heading=new QLabel(caption); heading->setAlignment(Qt::AlignCenter); heading->setMinimumHeight(28);
        column->addWidget(heading); column->addWidget(view,1); if(label) *label=heading;
        splitter->addWidget(widget);
    };
    pane(m_left,"英文原文"); pane(m_right,"中文译文",&m_translationCaption); layout->addWidget(splitter,1);
    auto hint=new QLabel("滚轮连续翻页 · ← / → / 空格翻页 · 阅读位置自动保存");
    hint->setStyleSheet("color:#64748b;"); layout->addWidget(hint);
    m_left->setDocument(m_original); m_right->setDocument(m_translated);
    for(auto view:{m_left,m_right}) {
        view->setPageMode(QPdfView::PageMode::SinglePage); view->setZoomMode(QPdfView::ZoomMode::FitToWidth);
        view->viewport()->installEventFilter(this);
        connect(view->pageNavigator(),&QPdfPageNavigator::currentPageChanged,this,[this](int page) {
            if(!m_synchronizing && page!=m_page) setPage(page+1);
        });
        connect(view->verticalScrollBar(),&QScrollBar::valueChanged,this,[this,view](int value) {
            if(m_synchronizing || !m_link->isChecked()) return;
            auto source=view->verticalScrollBar(); auto target=(view==m_left ? m_right : m_left)->verticalScrollBar();
            if(source->maximum()<=source->minimum()) return;
            m_scrollRatio=double(value-source->minimum())/(source->maximum()-source->minimum());
            QScopedValueRollback<bool> guard(m_synchronizing,true);
            target->setValue(target->minimum()+qRound(m_scrollRatio*(target->maximum()-target->minimum())));
        });
        connect(view->verticalScrollBar(),&QScrollBar::rangeChanged,this,[this] { restoreScroll(); });
    }
    connect(back,&QPushButton::clicked,this,&ReaderWidget::backRequested);
    connect(previous,&QPushButton::clicked,this,[this] { setPage(m_page); });
    connect(next,&QPushButton::clicked,this,[this] { setPage(m_page+2); });
    connect(m_pageSpin,qOverload<int>(&QSpinBox::valueChanged),this,&ReaderWidget::setPage);
    connect(m_zoom,qOverload<int>(&QSpinBox::valueChanged),this,[this](int percent) {
        QScopedValueRollback<bool> guard(m_synchronizing,true);
        for(auto view:{m_left,m_right}) { view->setZoomMode(QPdfView::ZoomMode::Custom); view->setZoomFactor(percent/100.); }
        QTimer::singleShot(0,this,&ReaderWidget::restoreScroll);
    });
    connect(m_left,&QPdfView::zoomFactorChanged,this,[this](qreal factor) {
        QSignalBlocker blocker(m_zoom); m_zoom->setValue(qRound(factor*100));
    });
    connect(fit,&QPushButton::clicked,this,[this] {
        for(auto view:{m_left,m_right}) view->setZoomMode(QPdfView::ZoomMode::FitToWidth);
        QTimer::singleShot(0,this,&ReaderWidget::restoreScroll);
    });
    connect(m_link,&QCheckBox::toggled,this,[this](bool enabled) { if(enabled) restoreScroll(); });
    connect(translate,&QPushButton::clicked,this,[this] { if(m_id) emit translationRequested(m_id); });
    connect(exportPdf,&QPushButton::clicked,this,[this] { if(m_id) emit exportRequested(m_id); });
    m_turnTimer.start();
}
void ReaderWidget::clear() {
    QScopedValueRollback<bool> guard(m_synchronizing,true);
    m_id=0; m_page=0; m_scrollRatio=0; m_original->close(); m_translated->close();
}
void ReaderWidget::openPaper(const Paper &paper) {
    clear();
    if(m_original->load(paper.originalPath)!=QPdfDocument::Error::None || m_original->pageCount()<1)
        throw std::runtime_error("无法打开原文 PDF");
    m_id=paper.id; m_title->setText(paper.title.left(70)); m_title->setToolTip(paper.title);
    m_pageSpin->setMaximum(m_original->pageCount()); m_total->setText(QString("/ %1").arg(m_original->pageCount()));
    refreshTranslation(paper); setPage(paper.lastPage);
}
void ReaderWidget::updateCaption(const Paper &paper) {
    if(m_translated->pageCount()>0) m_translationCaption->setText("中文译文");
    else if(paper.status=="queued") m_translationCaption->setText("等待翻译");
    else if(paper.status=="translating") m_translationCaption->setText(QString("正在翻译 · %1%").arg(paper.progress));
    else m_translationCaption->setText(paper.status=="failed" ? "翻译失败，可重新翻译" : "尚未翻译 · 点击上方「翻译」");
    m_translationCaption->setToolTip(paper.error);
}
void ReaderWidget::releaseTranslation(qint64 id) {
    if(id!=m_id) return;
    QScopedValueRollback<bool> guard(m_synchronizing,true); m_translated->close();
}
void ReaderWidget::refreshTranslation(const Paper &paper) {
    if(paper.id!=m_id) return;
    if(paper.status!="translating" && m_translated->pageCount()==0 && QFileInfo::exists(paper.translatedPath)) {
        QScopedValueRollback<bool> guard(m_synchronizing,true);
        m_translated->load(paper.translatedPath);
        if(m_translated->pageCount()>m_page) m_right->pageNavigator()->jump(m_page,{});
        QTimer::singleShot(0,this,&ReaderWidget::restoreScroll);
    }
    updateCaption(paper);
}
void ReaderWidget::setPage(int page) {
    if(!m_id || m_original->pageCount()<1) return;
    const int target=qBound(1,page,m_original->pageCount())-1;
    QScopedValueRollback<bool> guard(m_synchronizing,true);
    m_page=target; m_scrollRatio=0;
    for(auto view:{m_left,m_right}) if(view->document()->pageCount()>target)
        view->pageNavigator()->jump(target,{});
    { QSignalBlocker blocker(m_pageSpin); m_pageSpin->setValue(target+1); }
    QTimer::singleShot(0,this,&ReaderWidget::restoreScroll);
    emit positionChanged(m_id,m_page+1);
}
void ReaderWidget::restoreScroll() {
    if(!m_link->isChecked()) return;
    QScopedValueRollback<bool> guard(m_synchronizing,true);
    for(auto view:{m_left,m_right}) {
        auto scroll=view->verticalScrollBar();
        scroll->setValue(scroll->minimum()+qRound(m_scrollRatio*(scroll->maximum()-scroll->minimum())));
    }
}
bool ReaderWidget::eventFilter(QObject *object,QEvent *event) {
    if(object!=m_left->viewport() && object!=m_right->viewport()) return QWidget::eventFilter(object,event);
    if(event->type()==QEvent::KeyPress) {
        auto key=static_cast<QKeyEvent *>(event)->key();
        if(key==Qt::Key_Right || key==Qt::Key_PageDown || key==Qt::Key_Space) { setPage(m_page+2); return true; }
        if(key==Qt::Key_Left || key==Qt::Key_PageUp) { setPage(m_page); return true; }
    }
    if(event->type()==QEvent::Wheel && m_id) {
        auto wheel=static_cast<QWheelEvent *>(event);
        if(wheel->modifiers().testFlag(Qt::ControlModifier)) {
            const int delta=wheel->pixelDelta().isNull() ? wheel->angleDelta().y() : wheel->pixelDelta().y();
            if(!delta) return false;
            m_zoom->setValue(m_zoom->value()+(delta>0 ? 10 : -10)); return true;
        }
        auto view=object==m_left->viewport() ? m_left : m_right;
        if(view->document()->pageCount()==0) return false;
        auto scroll=view->verticalScrollBar();
        int dy=wheel->pixelDelta().isNull() ? wheel->angleDelta().y() : wheel->pixelDelta().y();
        const bool next=dy<0 && scroll->value()>=scroll->maximum();
        const bool previous=dy>0 && scroll->value()<=scroll->minimum();
        if(next || previous) {
            if(m_turnTimer.elapsed()>200 && ((next && m_page+1<m_original->pageCount()) || (previous && m_page>0))) {
                setPage(m_page+(next ? 2 : 0));
                m_scrollRatio=previous ? 1 : 0; QTimer::singleShot(0,this,&ReaderWidget::restoreScroll); m_turnTimer.restart();
            }
            return true;
        }
    }
    return QWidget::eventFilter(object,event);
}
