#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <vector>
#include <string>

namespace py = pybind11;

class CompactBook {
public:
    CompactBook() = default;

    void process_market_update(py::dict update) {
        if (update.contains("bids")) {
            update_side(update["bids"], bid_prices, bid_qtys);
        }
        if (update.contains("asks")) {
            update_side(update["asks"], ask_prices, ask_qtys);
        }
    }

    py::object best_bid() const {
        if (bid_prices.empty()) {
            return py::none();
        }
        return py::float_(bid_prices.back());
    }

    py::object best_ask() const {
        if (ask_prices.empty()) {
            return py::none();
        }
        return py::float_(ask_prices.front());
    }

    py::list get_top_levels(const std::string &side, int n) const {
        py::list result;
        if (n <= 0) {
            return result;
        }

        if (side == "BUY") {
            int count = std::min<int>(n, static_cast<int>(bid_prices.size()));
            for (int i = 0; i < count; ++i) {
                int idx = static_cast<int>(bid_prices.size()) - 1 - i;
                result.append(py::make_tuple(bid_prices[idx], bid_qtys[idx]));
            }
        } else {
            int count = std::min<int>(n, static_cast<int>(ask_prices.size()));
            for (int i = 0; i < count; ++i) {
                result.append(py::make_tuple(ask_prices[i], ask_qtys[i]));
            }
        }
        return result;
    }

private:
    std::vector<double> bid_prices;
    std::vector<double> bid_qtys;
    std::vector<double> ask_prices;
    std::vector<double> ask_qtys;

    void update_side(py::handle side_data, std::vector<double> &prices, std::vector<double> &qtys) {
        if (side_data.is_none()) {
            return;
        }

        for (auto item : py::cast<py::sequence>(side_data)) {
            auto level = py::cast<py::sequence>(item);
            double price = py::float_(level[0]);
            double qty = py::float_(level[1]);

            auto it = std::lower_bound(prices.begin(), prices.end(), price);
            if (qty > 0.0) {
                if (it == prices.end() || *it != price) {
                    int index = static_cast<int>(std::distance(prices.begin(), it));
                    prices.insert(it, price);
                    qtys.insert(qtys.begin() + index, qty);
                } else {
                    int index = static_cast<int>(std::distance(prices.begin(), it));
                    qtys[index] = qty;
                }
            } else {
                if (it != prices.end() && *it == price) {
                    int index = static_cast<int>(std::distance(prices.begin(), it));
                    prices.erase(prices.begin() + index);
                    qtys.erase(qtys.begin() + index);
                }
            }
        }
    }
};

PYBIND11_MODULE(_compactbook, m) {
    py::class_<CompactBook>(m, "CompactBook")
        .def(py::init<>())
        .def("process_market_update", &CompactBook::process_market_update)
        .def("best_bid", &CompactBook::best_bid)
        .def("best_ask", &CompactBook::best_ask)
        .def("get_top_levels", &CompactBook::get_top_levels, py::arg("side"), py::arg("n"));
}
