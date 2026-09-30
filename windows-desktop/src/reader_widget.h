#pragma once
#include <QElapsedTimer>
#include <QWidget>
#include "paper_repository.h"
class QPdfDocument;
class QPdfView;
class QSpinBox;
class QLabel;
class QCheckBox;

class ReaderWidget : public QWidget {
    Q_OBJECT
public:
    explicit ReaderWidget(QWidget *parent=nullptr);
    void openPaper(const Paper &paper);
    void clear();
    void releaseTranslation(qint64 id);
    void refreshTranslation(const Paper &paper);
    qint64 paperId() const { return m_id; }
    int currentPage() const { return m_page+1; }
    void setPage(int page);
signals:
    void backRequested();
    void translationRequested(qint64 id);
    void exportRequested(qint64 id);
    void positionChanged(qint64 id,int page);
private:
    bool eventFilter(QObject *object,QEvent *event) override;
    void restoreScroll();
    void updateCaption(const Paper &paper);
    QPdfDocument *m_original,*m_translated;
    QPdfView *m_left,*m_right;
    QSpinBox *m_pageSpin,*m_zoom;
    QLabel *m_title,*m_total,*m_translationCaption;
    QCheckBox *m_link;
    qint64 m_id=0;
    int m_page=0;
    double m_scrollRatio=0;
    bool m_synchronizing=false;
    QElapsedTimer m_turnTimer;
};
