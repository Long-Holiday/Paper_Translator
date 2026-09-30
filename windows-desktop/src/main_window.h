#pragma once
#include <QMainWindow>
#include "paper_repository.h"
#include "translation_controller.h"
class ReaderWidget;
class QTableWidget;
class QLineEdit;
class QStackedWidget;
class QPushButton;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget *parent=nullptr);
protected:
    void closeEvent(QCloseEvent *event) override;
private:
    void reload();
    qint64 selectedId() const;
    void openPaper(qint64 id);
    void translate(qint64 id);
    void exportPdf(qint64 id);
    void showError(const std::exception &error);
    PaperRepository m_repository;
    TranslationController m_translations;
    QStackedWidget *m_stack;
    QTableWidget *m_table;
    QLineEdit *m_search;
    ReaderWidget *m_reader;
    QPushButton *m_open,*m_translate,*m_cancel,*m_delete,*m_export;
};
