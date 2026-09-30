#include "app_paths.h"
#include "main_window.h"
#include <QApplication>
#include <QCommandLineParser>
#include <QFile>
#include <QLockFile>
#include <QMessageBox>
#include <QTimer>
#include <iostream>

int main(int argc,char *argv[]) {
    QApplication app(argc,argv);
    QCoreApplication::setApplicationName("PaperTranslator"); QCoreApplication::setApplicationVersion("2.0.0");
    QCommandLineParser parser; parser.setApplicationDescription("Paper Translator C++ / Qt 桌面版"); parser.addHelpOption(); parser.addVersionOption();
    parser.addOption({"smoke-test","启动并自动退出，检查 Qt、PDF 与 SQLite 运行库"}); parser.process(app);
    const bool smoke=parser.isSet("smoke-test");
    try {
        const auto root=AppPaths::userRoot();
        QLockFile lock(root+"/desktop.lock");
        if(!lock.tryLock(0)) {
            if(!smoke) QMessageBox::information(nullptr,"Paper Translator","程序已在运行，请切换到已有窗口。");
            return smoke ? 1 : 0;
        }
        MainWindow window;
        window.show();
        if(smoke) QTimer::singleShot(300,&window,&QWidget::close);
        return app.exec();
    } catch(const std::exception &exc) {
        if(smoke) std::cerr<<exc.what()<<std::endl;
        else QMessageBox::critical(nullptr,"启动失败",QString::fromUtf8(exc.what()));
        return 1;
    }
}
